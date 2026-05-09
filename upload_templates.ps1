﻿
$ftpServer = "192.168.0.130"
$ftpPort = 21
$username = "hassio"
$password = "2zCMbIdjPbjnxX"

$localFilePath = Join-Path $PWD "templates.yaml"
$remoteFilePath = "config/templates.yaml"
$ftpUrl = "ftp://${ftpServer}:${ftpPort}/${remoteFilePath}"

Write-Host "正在上传 templates.yaml..."

try {
    $request = [System.Net.FtpWebRequest]::Create($ftpUrl)
    $request.Credentials = New-Object System.Net.NetworkCredential($username, $password)
    $request.Method = [System.Net.WebRequestMethods+Ftp]::UploadFile
    $request.UsePassive = $true
    $request.UseBinary = $false

    $fileContent = [System.IO.File]::ReadAllBytes($localFilePath)
    $request.ContentLength = $fileContent.Length

    $requestStream = $request.GetRequestStream()
    $requestStream.Write($fileContent, 0, $fileContent.Length)
    $requestStream.Close()

    $response = $request.GetResponse()
    Write-Host "✓ templates.yaml 上传成功!"
    $response.Close()
} catch {
    Write-Host "✗ 上传失败: $_"
}

Write-Host ""
Write-Host "下一步：请在 Home Assistant 中重载配置！"
Write-Host "然后我们强制重置 Utility Meter！"
