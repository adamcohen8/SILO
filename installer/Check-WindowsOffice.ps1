param([ValidateSet('word-control','word','excel','powerpoint','powerpoint-control')][string]$Kind,[string]$Root,[string]$Output)
$ErrorActionPreference='Stop'
$started=Get-Date
$names=@{'word-control'='WINWORD';word='WINWORD';excel='EXCEL';powerpoint='POWERPNT';'powerpoint-control'='POWERPNT'}
$name=$names[$Kind]
$report=@{kind=$Kind;checks=@{};errors=@();scope='native Office environment/compatibility; synthetic format fixture; approval/model provenance belongs to the caller'}
$app=$document=$null
function Save-Owner {
 $owned=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq ($name+'.EXE') -and $_.CreationDate -ge $started -and ($_.CommandLine -like '*/Automation*' -or $_.CommandLine -like '*-Embedding*')})
 if ($owned.Count -eq 1) {$owned[0] | Select-Object Name,ProcessId,CreationDate,@{Name='StartTimeUtcTicks';Expression={(Get-Process -Id $_.ProcessId).StartTime.ToUniversalTime().Ticks}} | ConvertTo-Json | Set-Content ($Output+'.owner.json') -Encoding utf8}
}
try {
 if (Get-Process $name -ErrorAction SilentlyContinue) {throw 'An existing Office instance prevents isolated testing'}
 if ($Kind -eq 'word-control') {
  $app=New-Object -ComObject Word.Application;Save-Owner;$app.Visible=$false;$app.DisplayAlerts=0;$app.AutomationSecurity=3
  $report.version=$app.Version;$document=$app.Documents.Add();$document.Content.Text='SYNTHETIC OFFICE POSITIVE CONTROL'
  $report.checks.new_empty_document=$document.Content.Text.Contains('SYNTHETIC OFFICE POSITIVE CONTROL')
 } elseif ($Kind -eq 'word') {
  $app=New-Object -ComObject Word.Application;Save-Owner;$app.Visible=$false;$app.DisplayAlerts=0;$app.AutomationSecurity=3
  $report.version=$app.Version;$document=$app.Documents.OpenNoRepairDialog((Join-Path $Root 'capacity.docx'),$false,$true,$false)
  $report.checks.values=$document.Content.Text.Contains('108 kg')
  $document.ExportAsFixedFormat((Join-Path $Root 'native-word.pdf'),17)
  $report.checks.pdf_export=Test-Path (Join-Path $Root 'native-word.pdf')
 } elseif ($Kind -eq 'powerpoint-control') {
  $app=New-Object -ComObject PowerPoint.Application;Save-Owner;$app.AutomationSecurity=3;$app.DisplayAlerts=1
  $report.version=$app.Version;$document=$app.Presentations.Add(0);$slide=$document.Slides.Add(1,12)
  $report.checks.new_empty_presentation=$document.Slides.Count -eq 1
  [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($slide)
 } elseif ($Kind -eq 'excel') {
  $app=New-Object -ComObject Excel.Application;Save-Owner;$app.Visible=$false;$app.DisplayAlerts=$false;$app.AutomationSecurity=3;$app.AskToUpdateLinks=$false
  $report.version=$app.Version;$document=$app.Workbooks.Open((Join-Path $Root 'capacity.xlsx'),0,$true)
  $sheet=$document.Worksheets.Item(1);$values=@();$formulas=0
  for ($r=1;$r -le $sheet.UsedRange.Rows.Count;$r++) {for ($c=1;$c -le $sheet.UsedRange.Columns.Count;$c++) {$cell=$sheet.Cells.Item($r,$c);$values+=[string]$cell.Value2;if ($cell.HasFormula) {$formulas++};[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($cell)}}
  $report.checks.values=$values.Contains('48') -and $values.Contains('60') -and $values.Contains('108');$report.checks.no_formulas=$formulas -eq 0;$report.checks.no_external_links=$null -eq $document.LinkSources(1)
  $document.ExportAsFixedFormat(0,(Join-Path $Root 'native-excel.pdf'));$report.checks.pdf_export=Test-Path (Join-Path $Root 'native-excel.pdf')
  [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($sheet)
 } else {
  $app=New-Object -ComObject PowerPoint.Application;Save-Owner;$app.AutomationSecurity=3;$app.DisplayAlerts=1
  $report.version=$app.Version;$document=$app.Presentations.Open((Join-Path $Root 'capacity.pptx'),-1,0,0)
  $text='';$geometry=$true
  for ($i=1;$i -le $document.Slides.Count;$i++) {$slide=$document.Slides.Item($i)
   for ($j=1;$j -le $slide.Shapes.Count;$j++) {$shape=$slide.Shapes.Item($j);if ($shape.HasTextFrame -and $shape.TextFrame.HasText) {$text+=$shape.TextFrame.TextRange.Text};if ($shape.Left -lt 0 -or $shape.Top -lt 0 -or $shape.Left+$shape.Width -gt $document.PageSetup.SlideWidth+.1 -or $shape.Top+$shape.Height -gt $document.PageSetup.SlideHeight+.1) {$geometry=$false};[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shape)}
   $slide.Export((Join-Path $Root ('native-slide-'+$i+'.png')),'PNG',1280,720);[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($slide)
  }
  $report.checks.values=$text.Contains('48') -and $text.Contains('60') -and $text.Contains('108');$report.checks.geometry=$geometry;$report.slides=$document.Slides.Count
 }
} catch {$report.errors+=$_.Exception.Message}
finally {
 try {if ($document) {if ($Kind -like 'powerpoint*') {$document.Close()} else {$document.Close(0)}}} catch {$report.errors+=('Close: '+$_.Exception.Message)}
 try {if ($app) {$app.Quit()}} catch {$report.errors+=('Quit: '+$_.Exception.Message)}
 foreach ($item in @($document,$app)) {if ($item) {try {[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($item)} catch {}}}
 $report | ConvertTo-Json -Depth 6 | Set-Content $Output -Encoding utf8
}