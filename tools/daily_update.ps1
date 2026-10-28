# 즉시로 데이터 매일 갱신: 발행 PC의 작업 스케줄러에서 호출하세요.
# 예: powershell -NoProfile -ExecutionPolicy Bypass -File daily_update.ps1
$ErrorActionPreference = 'Continue'
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent)

# OC 키는 다음 중 하나로: (1) 설정에 저장해두면 생략, (2) 아래 주석 해제
# $env:IMMEDIATELYLAW_OC = '본인OC키'

python -m tools.publisher update  *>> data\daily.log
python -m tools.publisher package *>> data\daily.log
python -m tools.push_dist --repo https://github.com/nazgregory/immediatelylaw-data.git `
    --msg ("daily " + (Get-Date -Format s)) *>> data\daily.log
