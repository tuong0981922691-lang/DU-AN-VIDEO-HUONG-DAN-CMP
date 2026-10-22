$ErrorActionPreference = 'Stop'
$jsonText = $env:CMP_WINRT_REQUEST
$request = ConvertFrom-Json -InputObject $jsonText
if (-not $request.output_path -or -not $request.text) { throw 'output_path and text are required' }
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$synthesizerType = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media, ContentType=WindowsRuntime]
$streamType = [Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media, ContentType=WindowsRuntime]
$voice = $synthesizerType::AllVoices | Where-Object { $_.DisplayName -eq 'Microsoft An' -and $_.Language -eq 'vi-VN' } | Select-Object -First 1
if (-not $voice) { throw 'Required offline voice Microsoft An (vi-VN) is not installed' }
$synthesizer = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$speechStream = $null
$readStream = $null
$fileStream = $null
try {
    $synthesizer.Voice = $voice
    $operation = $synthesizer.SynthesizeTextToStreamAsync([string]$request.text)
    $asTaskMethod = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -like 'IAsyncOperation*'
    } | Select-Object -First 1
    if (-not $asTaskMethod) { throw 'WinRT async bridge is unavailable' }
    $task = $asTaskMethod.MakeGenericMethod($streamType).Invoke($null, @($operation))
    $speechStream = $task.GetAwaiter().GetResult()
    $readStream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($speechStream.GetInputStreamAt(0))
    $fileStream = [System.IO.File]::Create([string]$request.output_path)
    $readStream.CopyTo($fileStream)
    $fileStream.Flush()
}
finally {
    if ($fileStream) { $fileStream.Dispose() }
    if ($readStream) { $readStream.Dispose() }
    if ($speechStream) { $speechStream.Dispose() }
    if ($synthesizer) { $synthesizer.Dispose() }
}
