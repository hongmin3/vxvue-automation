# -*- coding: utf-8 -*-
"""XIPL.STUDIO WPF UI Automation bridge.

Studio는 WPF라 Win32 ``EnumChildWindows``로 내부를 읽을 수 없지만 Windows에
기본 포함된 .NET UI Automation에는 영상 탭, 파라미터 창, 값 편집기와 Process
버튼이 노출된다. 별도 pip 패키지를 추가하지 않고 PowerShell의
``UIAutomationClient``를 짧게 호출한다.

실측(2026-08-26): ``Contrast`` 5→6 변경 후 Process 시 영상 SSIM 0.99866,
5로 원복·재처리하면 기준 영상과 SSIM 1.00000. 이 모듈은 그 경로만 사용하며
파라미터 파일 자체를 저장하거나 덮어쓰지 않는다.
"""

import base64
import json
import os
import subprocess


class StudioError(RuntimeError):
    pass


_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

function RectArray($el) {
  $b = $el.Current.BoundingRectangle
  return @([int]$b.Left, [int]$b.Top, [int]$b.Right, [int]$b.Bottom)
}
function Elements($root, $type) {
  $c = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty, $type)
  return $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $c)
}
function FindParamWindow($root) {
  foreach ($w in (Elements $root ([System.Windows.Automation.ControlType]::Window))) {
    if ($w.Current.Name -like '[[]PI[]]*') { return $w }
  }
  return $null
}
function FindProcess($param) {
  foreach ($b in (Elements $param ([System.Windows.Automation.ControlType]::Button))) {
    if ($b.Current.Name -eq 'Process') { return $b }
  }
  return $null
}
function FindParameterEdit($param, $wanted) {
  foreach ($e in (Elements $param ([System.Windows.Automation.ControlType]::Edit))) {
    $cur = $e; $row = $null
    for ($i=0; $i -lt 6; $i++) {
      $cur = [System.Windows.Automation.TreeWalker]::RawViewWalker.GetParent($cur)
      if ($null -eq $cur) { break }
      if ($cur.Current.ControlType -eq [System.Windows.Automation.ControlType]::ListItem) {
        $row = $cur; break
      }
    }
    if ($null -ne $row) {
      foreach ($t in (Elements $row ([System.Windows.Automation.ControlType]::Text))) {
        if ($t.Current.Name -eq $wanted) { return $e }
      }
    }
  }
  return $null
}
function Snapshot($root, $param, $wanted) {
  $tab = ''
  foreach ($t in (Elements $root ([System.Windows.Automation.ControlType]::Text))) {
    if ($t.Current.Name -match '\.(img|dcm)$') { $tab = $t.Current.Name; break }
  }
  $status = ''
  foreach ($t in (Elements $param ([System.Windows.Automation.ControlType]::Text))) {
    if ($t.Current.Name -like 'Process PI*') { $status = $t.Current.Name; break }
  }
  $imageRect = $null
  foreach ($c in (Elements $root ([System.Windows.Automation.ControlType]::Custom))) {
    if ($c.Current.ClassName -eq 'ImageView') { $imageRect = RectArray $c; break }
  }
  $edit = FindParameterEdit $param $wanted
  $value = $null
  if ($null -ne $edit) {
    $vp = $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    $value = $vp.Current.Value
  }
  $process = FindProcess $param
  return [ordered]@{
    ok = ($null -ne $param -and $tab -ne '' -and $null -ne $process)
    parameter_title = $param.Current.Name
    image_tab = $tab
    parameter = $wanted
    value = $value
    process_enabled = if ($null -ne $process) { $process.Current.IsEnabled } else { $false }
    process_status = $status
    image_rect = $imageRect
    parameter_rect = RectArray $param
  }
}

try {
  $p = Get-Process 'XIPL.STUDIO' | Select-Object -First 1
  $root = [System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
  $param = FindParamWindow $root
  if ($null -eq $param) { throw '적용 파라미터 창([PI] - *.pi)을 찾지 못했습니다.' }
  $wanted = $env:VXVUE_UIA_PARAMETER
  if ([string]::IsNullOrWhiteSpace($wanted)) { $wanted = 'Contrast' }

  if ($env:VXVUE_UIA_ACTION -eq 'set') {
    $edit = FindParameterEdit $param $wanted
    if ($null -eq $edit) { throw "파라미터 '$wanted' Edit를 찾지 못했습니다." }
    $vp = $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    $before = $vp.Current.Value
    $vp.SetValue($env:VXVUE_UIA_VALUE)

    # 값 변경 자체가 한 차례 비동기 미리보기를 시작한다. 그 처리가 끝나 Process가
    # 다시 활성화된 뒤 체크리스트가 요구하는 Process를 명시적으로 한 번 누른다.
    $process = FindProcess $param
    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline -and -not $process.Current.IsEnabled) {
      Start-Sleep -Milliseconds 250
    }
    if (-not $process.Current.IsEnabled) { throw '값 변경 후 Process가 45초 안에 활성화되지 않았습니다.' }
    $process.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    Start-Sleep -Milliseconds 300
    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline -and -not $process.Current.IsEnabled) {
      Start-Sleep -Milliseconds 250
    }
    if (-not $process.Current.IsEnabled) { throw '명시적 Process가 45초 안에 완료되지 않았습니다.' }
    $snap = Snapshot $root $param $wanted
    $snap['before_value'] = $before
    $snap['changed_value'] = $vp.Current.Value
    $snap['processed'] = $true
    $snap | ConvertTo-Json -Compress -Depth 5
  } else {
    (Snapshot $root $param $wanted) | ConvertTo-Json -Compress -Depth 5
  }
} catch {
  [ordered]@{ok=$false; error=$_.Exception.Message} | ConvertTo-Json -Compress
}
'''


def _run(action="inspect", parameter="Contrast", value=None, timeout=110):
    encoded = base64.b64encode(_SCRIPT.encode("utf-16-le")).decode("ascii")
    env = os.environ.copy()
    env["VXVUE_UIA_ACTION"] = action
    env["VXVUE_UIA_PARAMETER"] = parameter
    if value is not None:
        env["VXVUE_UIA_VALUE"] = str(value)
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True, text=True, timeout=timeout, env=env)
    lines = [line.strip() for line in (proc.stdout or "").splitlines()
             if line.strip().startswith("{")]
    if not lines:
        raise StudioError((proc.stderr or proc.stdout or "UI Automation 출력 없음").strip())
    data = json.loads(lines[-1])
    if not data.get("ok"):
        raise StudioError(data.get("error") or "XIPL Studio 상태 확인 실패")
    return data


def inspect(parameter="Contrast"):
    """로드된 영상·파라미터 파일·Process 상태와 파라미터 값을 반환한다."""
    return _run("inspect", parameter=parameter)


def set_and_process(value, parameter="Contrast"):
    """파라미터 값을 설정하고 미리보기 완료 뒤 Process를 명시적으로 실행한다."""
    return _run("set", parameter=parameter, value=value)
