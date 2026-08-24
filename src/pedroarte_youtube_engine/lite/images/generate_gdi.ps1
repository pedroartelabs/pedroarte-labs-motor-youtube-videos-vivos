<#
  Gate 2 -- imagem de prova via GDI+ (System.Drawing), 100% local, custo zero.

  NAO e geracao de imagem por IA. E a estrategia "local" do ImageGenerationPort
  escolhida deliberadamente para o Gate 2 (decisao humana registrada em
  provenance): prova que FFmpeg/Ken Burns/mux funcionam com uma imagem real,
  sem gastar em nenhuma API externa. Geracao de imagem por IA fica para o
  Gate 3, com autorizacao explicita de custo.

  Toda aritmetica e resolvida em variaveis antes de qualquer chamada de
  construtor, e todo construtor usa `-ArgumentList` explicito: a sintaxe
  `New-Object Tipo(a, b - c, d)` e ambigua no parser do PowerShell quando um
  argumento contem uma subtracao, e falha com "op_Subtraction not found".
#>
param(
    [Parameter(Mandatory = $true)][string]$TitlePath,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [int]$Width = 1920,
    [int]$Height = 1080
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

$lines = Get-Content -Path $TitlePath -Encoding UTF8
$title = $lines[0]
$subtitle = if ($lines.Count -gt 1) { $lines[1] } else { "" }

$bitmap = New-Object -TypeName System.Drawing.Bitmap -ArgumentList $Width, $Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

# Gradiente diagonal — azul-petroleo escuro para ambar, evocando luz de
# lampiao contra uma oficina a noite (tema do exemplo do proprio repositorio).
$colorTop = [System.Drawing.Color]::FromArgb(255, 12, 24, 38)
$colorBottom = [System.Drawing.Color]::FromArgb(255, 122, 74, 26)
$rect = New-Object -TypeName System.Drawing.Rectangle -ArgumentList 0, 0, $Width, $Height
$brush = New-Object -TypeName System.Drawing.Drawing2D.LinearGradientBrush -ArgumentList $rect, $colorTop, $colorBottom, 45
$graphics.FillRectangle($brush, $rect)

# Vinheta simples: um circulo radial mais escuro nas bordas.
$vignetteX = [double]($Width * -0.2)
$vignetteY = [double]($Height * -0.2)
$vignetteW = [double]($Width * 1.4)
$vignetteH = [double]($Height * 1.4)
$vignette = New-Object -TypeName System.Drawing.Drawing2D.GraphicsPath
$vignette.AddEllipse($vignetteX, $vignetteY, $vignetteW, $vignetteH)
$vignetteBrush = New-Object -TypeName System.Drawing.Drawing2D.PathGradientBrush -ArgumentList (, $vignette)
$vignetteBrush.CenterColor = [System.Drawing.Color]::FromArgb(0, 0, 0, 0)
$vignetteBrush.SurroundColors = @([System.Drawing.Color]::FromArgb(90, 0, 0, 0))
$graphics.FillRectangle($vignetteBrush, $rect)

# Titulo centralizado, com sombra leve para legibilidade.
$titleFont = New-Object -TypeName System.Drawing.Font -ArgumentList "Georgia", 64, ([System.Drawing.FontStyle]::Bold)
$subtitleFont = New-Object -TypeName System.Drawing.Font -ArgumentList "Georgia", 30, ([System.Drawing.FontStyle]::Italic)
$whiteBrush = New-Object -TypeName System.Drawing.SolidBrush -ArgumentList ([System.Drawing.Color]::FromArgb(255, 245, 238, 224))
$shadowBrush = New-Object -TypeName System.Drawing.SolidBrush -ArgumentList ([System.Drawing.Color]::FromArgb(160, 0, 0, 0))

$format = New-Object -TypeName System.Drawing.StringFormat
$format.Alignment = [System.Drawing.StringAlignment]::Center
$format.LineAlignment = [System.Drawing.StringAlignment]::Center

$marginX = 80.0
$titleWidth = [double]($Width - 160)
$titleY = [double](($Height / 2.0) - 140)
$titleYShadow = [double](($Height / 2.0) - 136)
$subtitleY = [double](($Height / 2.0) + 40)

$titleRect = New-Object -TypeName System.Drawing.RectangleF -ArgumentList $marginX, $titleY, $titleWidth, 160.0
$titleRectShadow = New-Object -TypeName System.Drawing.RectangleF -ArgumentList ($marginX + 4.0), $titleYShadow, $titleWidth, 160.0
$graphics.DrawString($title, $titleFont, $shadowBrush, $titleRectShadow, $format)
$graphics.DrawString($title, $titleFont, $whiteBrush, $titleRect, $format)

if ($subtitle -ne "") {
    $subtitleRect = New-Object -TypeName System.Drawing.RectangleF -ArgumentList $marginX, $subtitleY, $titleWidth, 80.0
    $graphics.DrawString($subtitle, $subtitleFont, $whiteBrush, $subtitleRect, $format)
}

$bitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)

$graphics.Dispose()
$bitmap.Dispose()
$vignetteBrush.Dispose()
$brush.Dispose()

Write-Output "OK"
