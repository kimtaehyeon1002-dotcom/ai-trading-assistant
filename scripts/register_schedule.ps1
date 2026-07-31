<#
.SYNOPSIS
    야간선물 자동 수집 작업을 Windows 작업 스케줄러에 등록한다(design/23 A).

.DESCRIPTION
    모닝리포트가 손으로 bat을 돌려야만 갱신되던 문제(design/23 P1)의 해결.
    하루 3회 run_desktop_auto.bat을 실행한다:

      ThBot-FuturesClose     15:50 월~금  지수선물 정규장 종가 확정(마감 15:45 직후).
                                          **그날 밤 등락률의 기준가**가 되므로 이 실행을
                                          놓친 날 밤은 기준가 폴백으로 내려간다(design/27).
      ThBot-NightFutures-AM  04:40 화~토  야간장 마감(05:00) 직전 = 밤사이 등락 확정치.
                                          이 값이 그날 06:30 모닝리포트에 실린다.
      ThBot-Sync-PM          22:30 월~금  야간장 초반 시세 + 당일 체결 동기화.

    요일이 어긋나 보이지만 의도된 것이다 — 월요일 밤 세션은 화요일 05:00에 끝나므로,
    "월요일 밤 데이터"를 받으려면 화요일 새벽에 돌아야 한다. 금요일 밤 세션의 확정치는
    토요일 04:40에 수집되어 월요일 아침 리포트까지 쓰인다(주말 만료 60h가 이를 덮는다).
    FuturesClose만 월~금인 이유는 종가가 정규장이 열린 날에만 생기기 때문이다.

.NOTES
    전제조건
      1. 키움 OpenAPI **자동 로그인** 저장(트레이 아이콘 → 계좌비밀번호 저장 → AUTO 체크).
         안 되어 있으면 로그인 창이 입력을 기다리다 120초 후 실패한다.
      2. 해당 시각에 PC가 켜져 있고 **사용자가 로그온되어 있어야** 한다(키움 OCX는 데스크톱
         세션이 필요하다 — LogonType Interactive). -WakeToRun으로 절전 해제를 시도하지만
         완전 종료(shutdown) 상태는 깨울 수 없다.
      3. 실행 결과는 sync_auto.log에 누적된다.

    UAC("사용자 계정 컨트롤") 창이 떠서 로그인이 타임아웃되던 문제
      키움 로그인은 버전처리 단계에서 관리자 권한을 요구할 수 있다. 일반 권한으로 실행하면
      UAC 승인 창이 뜬 채로 대기하다가 CommConnect가 120초 타임아웃으로 실패한다(실제 사고:
      sync_auto.log의 '로그인 미완료(타임아웃 120s)' → 그날 키움 계좌 결측).
      작업 스케줄러는 UAC를 우회할 수 있는 신뢰된 승격 경로이므로, -RunLevel Highest로
      등록해 **승인 창 없이** 관리자 권한으로 실행되게 한다. UAC 자체를 끄는 방법(시스템 전역
      보안 약화)은 쓰지 않는다.
      ※ 이 스크립트는 **관리자 PowerShell에서 실행**해야 한다(Highest 등록에 승격 필요).
      ※ 손으로 돌릴 때도 UAC를 피하려면 bat을 직접 더블클릭하지 말고
         Start-ScheduledTask -TaskName ThBot-Sync-PM 으로 실행한다.

    등록:  (관리자 PowerShell) powershell -ExecutionPolicy Bypass -File scripts\register_schedule.ps1
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
        Name        = 'ThBot-FuturesClose'
        Time        = '15:50'
        Days        = 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'
        Description = '지수선물 정규장 종가 확정(그날 밤 등락률 기준가) - design/27'
    },
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

# 승격 실행(UAC 창 없이) — 자세한 배경은 상단 .NOTES 참조.
# LogonType Interactive: 키움 OCX가 데스크톱 세션을 요구하므로 로그온 상태에서만 돈다
# ("로그온 여부에 관계없이 실행"으로 바꾸면 세션 0에서 돌아 OCX가 뜨지 않는다).
$CurrentUser = "$env:USERDOMAIN\$env:USERNAME"
$Principal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType Interactive -RunLevel Highest

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    throw '관리자 권한이 필요합니다 — PowerShell을 "관리자 권한으로 실행"한 뒤 다시 시도하세요. ' +
          '(RunLevel Highest로 등록해야 실행 때 UAC 창이 뜨지 않습니다)'
}

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
        -Principal $Principal `
        -Description $t.Description | Out-Null

    $next = (Get-ScheduledTask -TaskName $t.Name | Get-ScheduledTaskInfo).NextRunTime
    Write-Host "등록됨: $($t.Name)  $($t.Time) $($t.Days -join ',')  → 다음 실행 $next"
}

Write-Host ''
Write-Host '확인:  Get-ScheduledTask -TaskName ''ThBot-*'' | Format-Table TaskName, State'
Write-Host '즉시 테스트:  Start-ScheduledTask -TaskName ThBot-NightFutures-AM'
Write-Host '실행 로그:  Get-Content sync_auto.log -Tail 40'
