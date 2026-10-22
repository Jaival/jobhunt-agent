# Converts .docx files to PDF with Microsoft Word, so the CV fonts (the font and fallback from config.yaml)
# render correctly. LibreOffice can't see per-user fonts on this PC and substitutes Segoe UI / Bodoni.
# Usage: powershell -ExecutionPolicy Bypass -File tools\docx2pdf.ps1 <file.docx | folder> [...]
# A folder converts every .docx inside it (recursively). The PDF is written next to each .docx.
param([Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)][string[]]$Paths)

$files = foreach ($p in $Paths) {
    $item = Get-Item -LiteralPath $p
    if ($item.PSIsContainer) { Get-ChildItem -LiteralPath $item.FullName -Recurse -Filter *.docx | Where-Object { $_.Name -notlike '~$*' } }
    else { $item }
}

# Word asks the Windows default printer for page layout. A network printer that can't be reached
# (e.g. a university printer while off campus) makes Word hang, so switch the default to
# "Microsoft Print to PDF" while converting and restore the original afterwards.
$pdfPrinter = 'Microsoft Print to PDF'
$original = Get-CimInstance Win32_Printer -Filter 'Default=TRUE' -ErrorAction SilentlyContinue
$switched = $false
if ($original -and $original.Name -ne $pdfPrinter) {
    $target = Get-CimInstance Win32_Printer | Where-Object { $_.Name -eq $pdfPrinter }
    if ($target) {
        [void](Invoke-CimMethod -InputObject $target -MethodName SetDefaultPrinter)
        $switched = $true
    }
}

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    foreach ($f in $files) {
        $pdf = [IO.Path]::ChangeExtension($f.FullName, '.pdf')
        $doc = $word.Documents.Open($f.FullName, $false, $true)
        $doc.SaveAs([ref]$pdf, [ref]17)   # 17 = wdFormatPDF
        $doc.Close(0)
        Write-Output "OK  $pdf"
    }
}
finally {
    try { $word.Quit() } catch {}
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    if ($switched) {
        $back = Get-CimInstance Win32_Printer | Where-Object { $_.Name -eq $original.Name }
        if ($back) { [void](Invoke-CimMethod -InputObject $back -MethodName SetDefaultPrinter) }
    }
}
