<#
  Gate 2 — sintese de narracao via Windows SAPI5 (System.Speech), 100% local,
  custo zero, sem nenhum pacote Python adicional.

  Le o texto de um arquivo (evita qualquer risco de injecao via linha de
  comando) e escreve um WAV real via SpeakToWaveFile.
#>
param(
    [Parameter(Mandatory = $true)][string]$TextPath,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [string]$VoiceName = ""
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Speech

$text = Get-Content -Path $TextPath -Raw -Encoding UTF8

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    if ($VoiceName -ne "") {
        $synth.SelectVoice($VoiceName)
    }
    $synth.SetOutputToWaveFile($OutputPath)
    $synth.Speak($text)
}
finally {
    $synth.SetOutputToNull()
    $synth.Dispose()
}

Write-Output "OK"
