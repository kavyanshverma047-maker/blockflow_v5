# Blockflow API Test Script
Write-Host '🚀 Testing Blockflow Exchange API...' -ForegroundColor Cyan

$random = Get-Random
$registerBody = @{
    username = \"testuser_$random\"
    email = \"test$random@example.com\"
    password = 'SecurePass123'
} | ConvertTo-Json

try {
    Write-Host '
1️⃣ Registering user...' -ForegroundColor Yellow
    $response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/auth/register' -Method POST -ContentType 'application/json' -Body $registerBody
    Write-Host \"✅ User registered: $($response.user.username)\" -ForegroundColor Green
    $token = $response.access_token
    
    $headers = @{ Authorization = \"Bearer $token\" }
    
    Write-Host '
2️⃣ Checking balance...' -ForegroundColor Yellow
    $balance = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/wallet/balance' -Method GET -Headers $headers
    Write-Host \"✅ Balance: ₹$($balance.balances.INR), $($balance.balances.USDT) USDT\" -ForegroundColor Green
    
    Write-Host '
3️⃣ Depositing 1000 USDT...' -ForegroundColor Yellow
    $depositBody = @{ currency = 'USDT'; amount = 1000.0 } | ConvertTo-Json
    $deposit = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/wallet/deposit' -Method POST -ContentType 'application/json' -Headers $headers -Body $depositBody
    Write-Host \"✅ New balance: $($deposit.new_balance) USDT\" -ForegroundColor Green
    
    Write-Host '
4️⃣ Placing spot order...' -ForegroundColor Yellow
    $orderBody = @{ pair = 'BTCUSDT'; side = 'buy'; amount = 0.01; price = 95000 } | ConvertTo-Json
    $order = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/spot/order' -Method POST -ContentType 'application/json' -Headers $headers -Body $orderBody
    Write-Host \"✅ Order placed: Trade ID $($order.trade.id)\" -ForegroundColor Green
    
    Write-Host '
🎉 All tests passed!' -ForegroundColor Cyan
} catch {
    Write-Host \"
❌ Error: $_\" -ForegroundColor Red
}
