# Turn a role-play script (demo/*.txt) into a recording with Windows text-to-speech, so the
# pipeline can be tested without recording a real meeting.
#
#   pwsh demo/make_audio.ps1 demo/brightmart.txt            -> demo/brightmart.wav (+ .ogg if ffmpeg is present)
#
# Script format: a "# voices: A=<voice>, B=<voice>" line, other "#" lines are comments,
# and every other line is "<label>: <what they say>".
param([Parameter(Mandatory = $true)][string]$Script)

Add-Type -AssemblyName System.Speech
$lines = Get-Content -LiteralPath $Script -Encoding UTF8
$voiceLine = $lines | Where-Object { $_ -match '^#\s*voices:' } | Select-Object -First 1
if (-not $voiceLine) { throw "No '# voices:' line in $Script" }
$voices = @{}
foreach ($pair in ($voiceLine -replace '^#\s*voices:\s*', '').Split(',')) {
    $k, $v = $pair.Split('=', 2)
    $voices[$k.Trim()] = $v.Trim()
}

$out = [System.IO.Path]::ChangeExtension((Resolve-Path -LiteralPath $Script).Path, '.wav')
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile($out)
foreach ($line in $lines) {
    if ($line -match '^\s*#' -or $line -notmatch '^\s*(\w+):\s*(.+)$') { continue }
    $label, $text = $Matches[1], $Matches[2]
    if (-not $voices.ContainsKey($label)) { throw "No voice for speaker '$label'" }
    $synth.SelectVoice($voices[$label])
    $pb = New-Object System.Speech.Synthesis.PromptBuilder
    $pb.AppendText($text)
    $pb.AppendBreak([TimeSpan]::FromMilliseconds(450))
    $synth.Speak($pb)
}
$synth.Dispose()
Write-Output "wrote $out"

if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    $ogg = [System.IO.Path]::ChangeExtension($out, '.ogg')
    ffmpeg -y -loglevel error -i $out -c:a libopus -b:a 24k $ogg
    Write-Output "wrote $ogg (send this to Telegram as an audio file)"
}
