param(
    [string]$message = "Update configuration"
)

# 添加所有文件
git add -A

# 提交
git commit -m "$message"

Write-Host "✅ Git提交完成: $message"
