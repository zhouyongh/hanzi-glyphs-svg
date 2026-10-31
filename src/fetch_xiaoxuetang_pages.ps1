<#
.SYNOPSIS
    小学堂页面抓取器（Windows 原生 TLS 客户端）。

.DESCRIPTION
    ASCDC 的边缘对 **xiaoxue.iis.sinica.edu.tw** 只放行 Windows 原生 TLS 客户端
    （PowerShell / .NET 的 SChannel）：同一份请求，Python 与 curl（OpenSSL）一律被
    nginx 以 405 挡在门外，PowerShell 则正常返回。因此本仓库把「页面」这一侧交给
    PowerShell 抓，图像那一侧（char.iis.sinica.edu.tw 的 ICS 渲染 API）仍走 Python。

    本脚本只做传输，不做解析；解析在 src/fetch_xiaoxuetang_glyphs.py。

.EXAMPLE
    # 抓检索结果第 1 页
    powershell -NoProfile -File src/fetch_xiaoxuetang_pages.ps1 -Mode search -Database chuwenzi -PageNo 1 -Out tmp/xxt/pages/page-001.html

.EXAMPLE
    # 抓某库的出處表（可能有多张表）
    powershell -NoProfile -File src/fetch_xiaoxuetang_pages.ps1 -Mode references -Database chuwenzi -Out tmp/xxt/references
#>
[CmdletBinding()]
param(
    [ValidateSet('search', 'references', 'license', 'stats', 'images')]
    [string]$Mode = 'search',

    [string]$Database = 'chuwenzi',

    # 跨字頭页号。**必须留空**：实测 PageNo=1 会让 ZiOrder 检索整体失效
    # （ZiOrder=2/100/3260 一律 0 命中；PageNo 留空则 ZiOrder=2 → 5 命中、
    # ZiOrder=3260 → 187 命中，与该字頭的实际字形数一致）。
    [string]$PageNo = '',

    [string]$ZiOrder = '',

    [string]$EudcFontChar = '',

    # 出處代号检索（实测：Reference=包 → 80 个字形 / 2 页）
    [string]$Reference = '',

    # 字頭内页号（实测：检索「一」7 页时 PageTo=1..7 内容各不相同，PageTo=8 为空）
    [int]$PageTo = 1,

    # 每页字形数。实测 400 可用（站点并不锁 50）：PerPage=400 一次取回字頭「一」的
    # 全部 319 个字形，与 50/页 翻 7 页得到的实例集合**逐条相同**。请求数少约一成。
    [int]$PerPage = 400,

    [string]$Out = '',

    # --Mode images 的清单文件：每行 pua<TAB>字体名<TAB>输出路径
    [string]$ListFile = '',

    # --Mode images 的取图尺寸（像素，实测 400 可用）
    [int]$Size = 200,

    [double]$Delay = 4.0,

    [int]$Retries = 5
)

$ErrorActionPreference = 'Continue'
$Host_ = 'https://xiaoxue.iis.sinica.edu.tw'
$UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

# 退出码：0 正常；3 地区封锁；4 IP 封锁；5 软拒（405 / block.html）；6 该页面不存在（404）
$EXIT_GEO = 3
$EXIT_IP = 4
$EXIT_SOFT = 5
$EXIT_NOPAGE = 6

function Get-Page {
    param(
        [string]$Url,
        [hashtable]$Fields,
        [string]$Referer
    )
    for ($attempt = 0; $attempt -lt $Retries; $attempt++) {
        $headers = @{
            'User-Agent'       = $UA
            'Accept-Language'  = 'zh-TW,zh;q=0.9'
        }
        if ($Referer) { $headers['Referer'] = $Referer }
        try {
            if ($null -ne $Fields) {
                $resp = Invoke-WebRequest -Uri $Url -Method POST -Body $Fields -UseBasicParsing `
                    -TimeoutSec 60 -Headers $headers
            }
            else {
                $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 60 -Headers $headers
            }
            $text = $resp.Content
            if ($text -match 'current country or region is not yet open') {
                Write-Host "GEO-BLOCK $Url"
                return @{ Code = $EXIT_GEO; Body = $text }
            }
            if ($text -match 'Your IP address has been blocked') {
                Write-Host "IP-BLOCK $Url"
                return @{ Code = $EXIT_IP; Body = $text }
            }
            return @{ Code = 0; Body = $text }
        }
        catch {
            $code = 0
            if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
            Write-Host ("SOFT-FAIL status={0} attempt={1}" -f $code, ($attempt + 1))
            if ($code -eq 405) { return @{ Code = $EXIT_SOFT; Body = '' } }
            # 404 是「这个库没有这个页面」，重试没有意义（各库的出處表路径并不统一：
            # 金文 / 小篆 就不叫 /Reference/Reference）
            if ($code -eq 404) { return @{ Code = $EXIT_NOPAGE; Body = '' } }
            Start-Sleep -Seconds ([Math]::Min(300, 5 * [Math]::Pow(2, $attempt)))
        }
    }
    return @{ Code = $EXIT_SOFT; Body = '' }
}

function Get-Binary {
    param(
        [string]$Url,
        [string]$Referer
    )
    for ($attempt = 0; $attempt -lt $Retries; $attempt++) {
        $headers = @{
            'User-Agent'       = $UA
            'Accept-Language'  = 'zh-TW,zh;q=0.9'
        }
        if ($Referer) { $headers['Referer'] = $Referer }
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 90 -Headers $headers
            $bytes = $resp.Content
            $ctype = [string]$resp.Headers['Content-Type']
            # 返回的是 HTML 就不是图片（多半是拦截页），不能当字形存下来
            if ($ctype -notlike 'image/*') {
                Write-Host "NOT-IMAGE ctype=$ctype"
                return @{ Code = $EXIT_SOFT; Body = $null }
            }
            return @{ Code = 0; Body = $bytes; Type = $ctype }
        }
        catch {
            $code = 0
            if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
            Write-Host ("SOFT-FAIL status={0} attempt={1}" -f $code, ($attempt + 1))
            if ($code -eq 405) { return @{ Code = $EXIT_SOFT; Body = $null } }
            if ($code -eq 404) { return @{ Code = $EXIT_SOFT; Body = $null } }
            Start-Sleep -Seconds ([Math]::Min(300, 5 * [Math]::Pow(2, $attempt)))
        }
    }
    return @{ Code = $EXIT_SOFT; Body = $null }
}

function Save-Page {
    param([string]$Text, [string]$Path)
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    # 逐字节写：页面是 UTF-8，PS 的默认编码不能用来存
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

$exit = 0

switch ($Mode) {
    'search' {
        $fields = @{
            EudcFontChar = $EudcFontChar
            ZiOrder      = "$ZiOrder"
            PageNo      = "$PageNo"
            PageTo      = "$PageTo"
            Reference   = "$Reference"
            PaginalZiNum = "$PerPage"
            ImageSize   = '36'
        }
        $r = Get-Page -Url "$Host_/$Database/PageResult/PageResult" -Fields $fields -Referer "$Host_/$Database/"
        if ($r.Code -ne 0) { exit $r.Code }
        Save-Page -Text $r.Body -Path $Out
        Write-Host ("SAVED {0} ({1} bytes)" -f $Out, (Get-Item $Out).Length)
    }

    'references' {
        $paths = @{
            'chuwenzi'  = @('/chuwenzi/Reference/Reference')
            'qinwenzi'  = @('/qinwenzi/Reference/Reference')
            'chuanchao' = @('/chuanchao/Reference/ChuanReference', '/chuanchao/Reference/HanJianReference')
            'jiaguwen'  = @('/jiaguwen/Reference/Reference')
            'jinwen'    = @('/jinwen/Reference/Reference')
            'lishu'     = @('/lishu/Reference/Reference')
            'xiaozhuan' = @('/xiaozhuan/Reference/Reference')
        }
        if (-not $paths.ContainsKey($Database)) { Write-Host "UNKNOWN-DB $Database"; exit 5 }
        $saved = 0
        foreach ($p in $paths[$Database]) {
            $name = ($p.Trim('/') -replace '/', '-') + '.html'
            $r = Get-Page -Url "$Host_$p" -Referer "$Host_/$Database/"
            # 404 = 这个库没有这一张出處表（金文 / 小篆 实测就是没有）。
            # 不是错误，记一笔跳过即可——归属闸门改走别的依据。
            if ($r.Code -eq $EXIT_NOPAGE) {
                Write-Host ("NO-REFERENCE-PAGE {0}" -f $p)
                Start-Sleep -Seconds $Delay
                continue
            }
            if ($r.Code -ne 0) { exit $r.Code }
            Save-Page -Text $r.Body -Path (Join-Path $Out $name)
            Write-Host ("SAVED {0} ({1} bytes)" -f (Join-Path $Out $name), (Get-Item (Join-Path $Out $name)).Length)
            $saved++
            Start-Sleep -Seconds $Delay
        }
        if ($saved -eq 0) { exit $EXIT_NOPAGE }
    }

    'license' {
        $r = Get-Page -Url "$Host_/License/License" -Referer "$Host_/"
        if ($r.Code -ne 0) { exit $r.Code }
        Save-Page -Text $r.Body -Path $Out
        Write-Host ("SAVED {0} ({1} bytes)" -f $Out, (Get-Item $Out).Length)
    }

    'stats' {
        $r = Get-Page -Url "$Host_/$Database/" -Referer "$Host_/"
        if ($r.Code -ne 0) { exit $r.Code }
        Save-Page -Text $r.Body -Path $Out
        Write-Host ("SAVED {0} ({1} bytes)" -f $Out, (Get-Item $Out).Length)
    }

    'images' {
        # 清单：pua<TAB>字体名<TAB>输出路径
        #
        # 两个要点（都是实测踩出来的）：
        # 1. **text 参数要传真正的 PUA 字符**（URL 编码），不是十六进制字符串。
        #    传 "E0A9" 会被当成四个字面字符渲染成 "E0A9" 四个字。
        # 2. **font 参数是必须的**：PUA 码位按字体分命名空间——同一个 E0A9，
        #    在「中研院楚系簡帛文字重文一」里是「一」的楚文字，在「…重文五」里是「天」。
        #    不带字体（或带错）取回来的图就是别的字。
        if (-not (Test-Path -LiteralPath $ListFile)) { Write-Host "NO-LIST $ListFile"; exit 5 }
        $lines = Get-Content -LiteralPath $ListFile -Encoding UTF8
        $i = 0
        $done = 0
        $skip = 0
        foreach ($line in $lines) {
            if (-not $line.Trim()) { continue }
            $i++
            $parts = $line -split "`t"
            if ($parts.Count -lt 3) { continue }
            $pua = $parts[0].Trim()
            $font = $parts[1]
            $dest = $parts[2].Trim()
            if ((Test-Path -LiteralPath $dest) -and ((Get-Item -LiteralPath $dest).Length -gt 0)) {
                $skip++
                continue
            }
            $dir = Split-Path -Parent $dest
            if ($dir -and -not (Test-Path -LiteralPath $dir)) {
                New-Item -ItemType Directory -Path $dir -Force | Out-Null
            }
            $cp = [Convert]::ToInt32($pua, 16)
            $text = [System.Uri]::EscapeDataString([string][char]$cp)
            $fontEsc = [System.Uri]::EscapeDataString($font)
            $url = "$Host_/ImageText2/ShowImage.ashx?text=$text&font=$fontEsc&size=$Size&style=regular&color=%23000000"
            $r = Get-Binary -Url $url -Referer "$Host_/$Database/"
            if ($r.Code -ne 0) { Write-Host ("IMAGE-FAIL {0} code={1}" -f $pua, $r.Code); exit $r.Code }
            [System.IO.File]::WriteAllBytes($dest, $r.Body)
            $done++
            if ($done % 50 -eq 0) { Write-Host ("IMG {0} done={1} skip={2} of={3}" -f $Database, $done, $skip, $i) }
            Start-Sleep -Seconds $Delay
        }
        Write-Host ("IMG {0} done={1} skip={2} total={3}" -f $Database, $done, $skip, $i)
    }
}

exit $exit
