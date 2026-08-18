# -*- coding: utf-8 -*-
"""VXvue DRF DB 조회 브릿지.

ODBC 드라이버/pyodbc 설치 없이 동작하도록 PowerShell + System.Data.SqlClient를
경유한다(Bellalun `auto/core/db.py`와 동일한 사상). VXvue는 Bellalun의
DATA/ACCOUNT/CONFIGURATION/PROCEDURE 4분리 구조와 달리 `.\\CHAMELEON`
인스턴스의 **DRF 단일 데이터베이스**를 쓴다(2026-08-18 실측).

조회 전용이다. UPDATE/INSERT/DELETE는 의도적으로 제공하지 않는다.
설정 변경은 반드시 제품 UI를 거쳐야 TC의 검증 의미가 유지된다.
"""

import json
import os
import shutil
import subprocess
import tempfile

_PS_QUERY = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$cs = "Server=$env:VX_SERVER;Database=$env:VX_DB;Integrated Security=True;Connect Timeout=15"
$conn = New-Object System.Data.SqlClient.SqlConnection($cs)
$conn.Open()
try {
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = $env:VX_SQL
    if ($env:VX_PARAMS) {
        $p = $env:VX_PARAMS | ConvertFrom-Json
        foreach ($k in $p.PSObject.Properties.Name) {
            $v = $p.$k
            if ($null -eq $v) { $v = [System.DBNull]::Value }
            [void]$cmd.Parameters.AddWithValue(('@' + $k), $v)
        }
    }
    $da = New-Object System.Data.SqlClient.SqlDataAdapter($cmd)
    $dt = New-Object System.Data.DataTable
    [void]$da.Fill($dt)
    $rows = @()
    foreach ($r in $dt.Rows) {
        $o = [ordered]@{}
        foreach ($col in $dt.Columns) {
            $val = $r[$col]
            if ($val -is [System.DBNull]) { $val = $null }
            $o[$col.ColumnName] = $val
        }
        $rows += [pscustomobject]$o
    }
    ConvertTo-Json -InputObject @($rows) -Depth 5 -Compress
} finally { $conn.Close() }
"""

_PS_BATCH = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$specs = Get-Content -LiteralPath $env:VX_SPEC_FILE -Raw -Encoding UTF8 | ConvertFrom-Json
$out = [ordered]@{}
$cs = "Server=$env:VX_SERVER;Database=$env:VX_DB;Integrated Security=True;Connect Timeout=15"
$conn = New-Object System.Data.SqlClient.SqlConnection($cs)
$conn.Open()
try {
    foreach ($s in $specs) {
        try {
            $cmd = $conn.CreateCommand()
            $cmd.CommandText = $s.sql
            $da = New-Object System.Data.SqlClient.SqlDataAdapter($cmd)
            $dt = New-Object System.Data.DataTable
            [void]$da.Fill($dt)
            $rows = @()
            foreach ($r in $dt.Rows) {
                $o = [ordered]@{}
                foreach ($col in $dt.Columns) {
                    $val = $r[$col]
                    if ($val -is [System.DBNull]) { $val = $null }
                    $o[$col.ColumnName] = $val
                }
                $rows += [pscustomobject]$o
            }
            $out[$s.name] = @($rows)
        } catch {
            $out[$s.name] = @{ _error = $_.Exception.Message }
        }
    }
} finally { $conn.Close() }
ConvertTo-Json -InputObject $out -Depth 6 -Compress |
    Out-File -LiteralPath $env:VX_OUT_FILE -Encoding UTF8
"""


class DbError(RuntimeError):
    pass


class VXvueDb:
    """DRF 조회기."""

    def __init__(self, server=r".\CHAMELEON", database="DRF"):
        self.server = server
        self.database = database

    def query(self, sql, params=None, database=None):
        env = dict(os.environ)
        env["VX_SERVER"] = self.server
        env["VX_DB"] = database or self.database
        env["VX_SQL"] = sql
        env["VX_PARAMS"] = json.dumps(params or {}, ensure_ascii=False)

        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_QUERY],
            capture_output=True, env=env,
        )
        out = proc.stdout.decode("utf-8", "replace").strip()
        err = proc.stderr.decode("utf-8", "replace").strip()
        if proc.returncode != 0:
            raise DbError("조회 실패: %s" % (err or out))
        if not out:
            return []
        try:
            data = json.loads(out)
        except json.JSONDecodeError as exc:
            raise DbError("응답 파싱 실패: %s / raw=%s" % (exc, out[:500]))
        return [data] if isinstance(data, dict) else data

    def query_many(self, specs):
        """[{"name":..., "sql":...}, ...] 를 PowerShell 1회 호출로 처리한다."""
        if not specs:
            return {}
        tmp = tempfile.mkdtemp(prefix="vx_")
        spec_file = os.path.join(tmp, "spec.json")
        out_file = os.path.join(tmp, "out.json")
        try:
            with open(spec_file, "w", encoding="utf-8") as f:
                json.dump(specs, f, ensure_ascii=False)
            env = dict(os.environ)
            env["VX_SERVER"] = self.server
            env["VX_DB"] = self.database
            env["VX_SPEC_FILE"] = spec_file
            env["VX_OUT_FILE"] = out_file
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_BATCH],
                capture_output=True, env=env,
            )
            if not os.path.exists(out_file):
                err = proc.stderr.decode("utf-8", "replace").strip()
                raise DbError("배치 조회 실패: %s" % (err or proc.stdout.decode("utf-8", "replace")))
            with open(out_file, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def one(self, sql, params=None):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql, params=None, default=None):
        row = self.one(sql, params)
        if not row:
            return default
        return next(iter(row.values()))

    def ping(self):
        """DRF 업무 DB 접속 가능 여부. master는 항상 열리므로 판정에 쓰지 않는다."""
        try:
            self.scalar("SELECT 1 AS ok")
            return True
        except DbError:
            return False

    # --- TC에서 자주 쓰는 조회 -------------------------------------------
    def ae_list(self, kind=None):
        """Setting > DICOM 에 등록된 SCP 목록.

        AE_LIST.Type 은 DICOM_MWL / DICOM_PRINT / DICOM_STORAGE 등이며
        `RemoveSBSC` 컬럼이 Extra Tool 화면의 체크 옵션과 대응한다
        (TC_WindowsUpdate_06 판정 근거, 2026-08-18 확인).
        """
        sql = ("SELECT AEListKey, DeleteStatus, Type, Name, Title, IP, Port, "
               "Selected, SearchCondition, RemoveSBSC FROM AE_LIST "
               "WHERE DeleteStatus = 0")
        if kind:
            sql += " AND Type = '%s'" % kind
        return self.query(sql + " ORDER BY AEListKey")

    def study_count(self):
        return self.scalar("SELECT COUNT(*) AS c FROM STUDY", default=0)

    def latest_studies(self, top=5):
        return self.query(
            "SELECT TOP %d s.StudyKey, p.PatientID, p.PatientName, s.AccessionNum, "
            "s.Modality, s.StudyDesc, s.StudyCreateDttm "
            "FROM STUDY s LEFT JOIN PATIENT p ON p.PatientKey = s.PatientKey "
            "ORDER BY s.StudyKey DESC" % top)

    def reserved_procedures(self, top=20):
        """MWL 조회로 가져온 예약 검사(Registration > Scheduled) 목록."""
        return self.query(
            "SELECT TOP %d * FROM RESERVED_PROCEDURE ORDER BY 1 DESC" % top)
