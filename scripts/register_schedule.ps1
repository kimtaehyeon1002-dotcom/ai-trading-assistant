<#
.SYNOPSIS
    야간선물 자동 수집 작업을 Windows 작업 스케줄러에 등록한다(design/23 A).

.DESCRIPTION
    모닝리포트가 손으로 bat을 돌려야만 갱신되던 문제(design/23 P1)의 해결.
    하루 2회 run_desktop_auto.bat을 실행한다:

      ThBot-NightFutures-AM  04:40 화~토  야간장 마감(05:00) 직전 = 밤사이 등락 확정치.
                                          이 값이 그날 06:30 모닝리포트에 실린다.
      ThBot-Sync-PM          22:30 월~금  야간장 초반 시세 + 당일 체결 동기화.

    요일이 어긋나 보이지만 의도된 것이다 — 월요일 밤 세션은 화요일 05:00에 끝나므로,
    "월요일 밤 데이터"를 받으려면 화요일 새벽에 돌아야 한다. 금요일 밤 세션의 확정치는
    토요일 04:40에 수집되어 월요일 아침 리포트까지 쓰인다(주말 만료 60h가 이를 덮는다).

.NOTES
    전제조건
      1. 키움 OpenAPI **자동 로그인** 저장(트레이 아이콘 → 계좌비밀번호 저장 → AUTO 체크).
         안 되어 있으면 로그인 창이 입력을 기다리다 120초 후 실패한다.
      2. 해당 시각에 PC가 켜져 있어야 한다. -WakeToRun으로 절전 해제를 시도하지만
         완전 종료(shutdown) 상태는 깨울 수 없다.
      3. 실행 결과는 sync_auto.log에 누적된다.

    등록:  powershell -ExecutionPolicy Bypass -File scripts\register_schedule.ps1
    해제:  powershell -ExecutionPolicy Bypass -File scripts\register_schedule.ps1 -Unregister
    확인:  Get-ScheduledTask -TaskName 'ThBot-*' | Format-Table TaskName, State
#>
[CmdletBinding()]
param(
    [switch]$Unregister
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BatPath = Join-Path $RepoRoot 'run_desktop_auto.bat'

$Tasks = @(
    @{
        Name        = 'ThBot-NightFutures-AM'
        Time        = '04:40'
        Days        = 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'
        Description = '야간선물 마감 직전 수집(모닝리포트 확정치) - design/23'
    },
    @{
        Name        = 'ThBot-Sync-PM'
        Time        = '22:30'
        Days        = 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'
        Description = '야간장 초반 시세 + 당일 체결 동기화 - design/23'
    }
)

if ($Unregister) {
    foreach ($t in $Tasks) {
        if (Get-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false
            Write-Host "해제됨: $($t.Name)"
        }
        else {
            Write-Host "없음(건너뜀): $($t.Name)"
        }
    }
    return
}

if (-not (Test-Path $BatPath)) {
    throw "run_desktop_auto.bat을 찾을 수 없습니다: $BatPath"
}

# 놓친 실행 보충 + 절전 해제. 실행 시간 상한을 두어 로그인 창이 떠 있는 채로 영구 점유하는
# 상황을 막는다(bat 자체 타임아웃과 이중 방어).
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

foreach ($t in $Tasks) {
    $action = New-ScheduledTaskAction -Execute $BatPath -WorkingDirectory $RepoRoot
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $t.Days -At $t.Time

    if (Get-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false   # 설정 변경분 반영
    }
    Register-ScheduledTask `
        -TaskName $t.Name `
        -Action $action `
        -Trigger $trigger `
        -Settings $Settings `
        -Description $t.Description | Out-Null

    $next = (Get-ScheduledTask -TaskName $t.Name | Get-ScheduledTaskInfo).NextRunTime
    Write-Host "등록됨: $($t.Name)  $($t.Time) $($t.Days -join ',')  → 다음 실행 $next"
}

Write-Host ''
Write-Host '확인:  Get-ScheduledTask -TaskName ''ThBot-*'' | Format-Table TaskName, State'
Write-Host '즉시 테스트:  Start-ScheduledTask -TaskName ThBot-NightFutures-AM'
Write-Host '실행 로그:  Get-Content sync_auto.log -Tail 40'
