function Get-RAAreaCodes {
    <#
    .SYNOPSIS
        Discovers Resident Advisor area codes using your local Flask API.
    
    .DESCRIPTION
        This function systematically tests area IDs to discover valid RA area codes by calling
        your local Flask API's area info functionality.
    
    .PARAMETER StartId
        Starting area ID to test (default: 1)
    
    .PARAMETER EndId
        Ending area ID to test (default: 1000)
    
    .PARAMETER ApiUrl
        Base URL of your Flask API (default: http://localhost:8080)
    
    .PARAMETER BatchSize
        Number of concurrent requests per batch (default: 10)
    
    .PARAMETER DelayMs
        Delay between batches in milliseconds (default: 300)
    
    .PARAMETER OutputPath
        Path to save the results as CSV (optional)
    
    .EXAMPLE
        Get-RAAreaCodes -StartId 1 -EndId 100 -OutputPath "ra_areas.csv"
    
    .EXAMPLE
        Get-RAAreaCodes -StartId 1 -EndId 500 -ApiUrl "http://localhost:5000"
    #>
    
    param(
        [int]$StartId = 1,
        [int]$EndId = 1000,
        [string]$ApiUrl = "http://localhost:8080",
        [int]$BatchSize = 10,
        [int]$DelayMs = 300,
        [string]$OutputPath = $null
    )
    
    $discoveredAreas = @()
    $totalIds = $EndId - $StartId + 1
    $processedCount = 0
    $foundCount = 0
    
    Write-Host "Starting RA area code discovery using your Flask API..." -ForegroundColor Green
    Write-Host "API URL: $ApiUrl" -ForegroundColor Cyan
    Write-Host "Testing area IDs from $StartId to $EndId ($totalIds total)" -ForegroundColor Cyan
    Write-Host "Batch size: $BatchSize, Delay: ${DelayMs}ms" -ForegroundColor Yellow
    Write-Host ""
    
    # Test API connectivity first
    try {
        $healthCheck = Invoke-RestMethod -Uri "$ApiUrl/" -Method Get -TimeoutSec 5
        Write-Host "API connectivity confirmed!" -ForegroundColor Green
        Write-Host ""
    }
    catch {
        Write-Host "ERROR: Cannot connect to your Flask API at $ApiUrl" -ForegroundColor Red
        Write-Host "Make sure your Flask app is running with: python app.py" -ForegroundColor Yellow
        return
    }
    
    # Process in batches to avoid overwhelming the API
    for ($batchStart = $StartId; $batchStart -le $EndId; $batchStart += $BatchSize) {
        $batchEnd = [Math]::Min($batchStart + $BatchSize - 1, $EndId)
        
        # Create jobs for current batch
        $jobs = @()
        for ($id = $batchStart; $id -le $batchEnd; $id++) {
            $job = Start-Job -ScriptBlock {
                param($Id, $BaseUrl)
                
                try {
                    # Call your Flask API's events endpoint with a dummy date to trigger area lookup
                    # This will use your existing get_area_info() function
                    $response = Invoke-RestMethod -Uri "$BaseUrl/events?area=$Id&start_date=2025-01-01&end_date=2025-01-01" -Method Get -TimeoutSec 10
                    
                    if ($response.area -and $response.area.name -and $response.area.name -ne "Unknown") {
                        return @{
                            Success = $true
                            Id = $response.area.id
                            Name = $response.area.name
                            UrlName = $response.area.url_name
                            CountryName = $response.area.country.name
                            CountryCode = $response.area.country.code
                        }
                    }
                    return @{ Success = $false; Id = $Id }
                }
                catch {
                    # If the events endpoint fails, that's expected for invalid areas
                    return @{ Success = $false; Id = $Id }
                }
            } -ArgumentList $id, $ApiUrl
            
            $jobs += $job
        }
        
        # Wait for all jobs in this batch to complete
        $batchResults = $jobs | Wait-Job | Receive-Job
        $jobs | Remove-Job
        
        # Process results
        foreach ($result in $batchResults) {
            $processedCount++
            
            if ($result.Success) {
                $foundCount++
                $areaInfo = [PSCustomObject]@{
                    AreaId = $result.Id
                    AreaName = $result.Name
                    UrlName = $result.UrlName
                    CountryName = $result.CountryName
                    CountryCode = $result.CountryCode
                    FullName = "$($result.Name), $($result.CountryCode)"
                }
                
                $discoveredAreas += $areaInfo
                
                Write-Host "Found: ID $($result.Id) - $($result.Name), $($result.CountryName) ($($result.CountryCode))" -ForegroundColor Green
            }
        }
        
        # Progress update
        $percentComplete = [Math]::Round(($processedCount / $totalIds) * 100, 1)
        Write-Progress -Activity "Discovering RA Area Codes" -Status "Processed $processedCount of $totalIds IDs - Found $foundCount areas" -PercentComplete $percentComplete
        
        # Delay between batches to be respectful to your API
        if ($batchStart + $BatchSize -le $EndId) {
            Start-Sleep -Milliseconds $DelayMs
        }
    }
    
    Write-Progress -Activity "Discovering RA Area Codes" -Completed
    Write-Host ""
    Write-Host "Discovery complete!" -ForegroundColor Green
    Write-Host "Found $($discoveredAreas.Count) valid area codes out of $totalIds tested" -ForegroundColor Cyan
    
    # Sort results by country, then by area name
    $discoveredAreas = $discoveredAreas | Sort-Object CountryName, AreaName
    
    # Display summary by country
    Write-Host ""
    Write-Host "Areas by Country:" -ForegroundColor Yellow
    $groupedByCountry = $discoveredAreas | Group-Object CountryName | Sort-Object Name
    foreach ($country in $groupedByCountry) {
        Write-Host "$($country.Name): $($country.Count) areas" -ForegroundColor White
        foreach ($area in $country.Group) {
            Write-Host "  ID $($area.AreaId): $($area.AreaName)" -ForegroundColor Gray
        }
    }
    
    # Save to CSV if path provided
    if ($OutputPath) {
        try {
            $discoveredAreas | Export-Csv -Path $OutputPath -NoTypeInformation -Encoding UTF8
            Write-Host ""
            Write-Host "Results saved to: $OutputPath" -ForegroundColor Green
        }
        catch {
            Write-Host ""
            Write-Host "Failed to save CSV: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    
    # Generate Python dictionary format for easy integration
    Write-Host ""
    Write-Host "Python dictionary format (for app integration):" -ForegroundColor Yellow
    Write-Host "AREA_CODES = {" -ForegroundColor Gray
    foreach ($area in $discoveredAreas) {
        $pythonLine = "    $($area.AreaId): `"$($area.FullName)`","
        Write-Host $pythonLine -ForegroundColor Gray
    }
    Write-Host "}" -ForegroundColor Gray
    
    # Generate JSON format
    Write-Host ""
    Write-Host "JSON format:" -ForegroundColor Yellow
    $jsonOutput = $discoveredAreas | ConvertTo-Json -Depth 3
    Write-Host $jsonOutput -ForegroundColor Gray
    
    return $discoveredAreas
}

# Helper function to search for specific countries or cities
function Find-RAAreaByName {
    param(
        [Parameter(Mandatory=$true)]
        [array]$Areas,
        
        [Parameter(Mandatory=$true)]
        [string]$SearchTerm
    )
    
    $results = $Areas | Where-Object { 
        $_.AreaName -like "*$SearchTerm*" -or 
        $_.CountryName -like "*$SearchTerm*" -or
        $_.CountryCode -like "*$SearchTerm*"
    }
    
    if ($results) {
        Write-Host "Found $($results.Count) match(es) for '$SearchTerm':" -ForegroundColor Green
        foreach ($result in $results) {
            Write-Host "  ID $($result.AreaId): $($result.AreaName), $($result.CountryName) ($($result.CountryCode))" -ForegroundColor White
        }
    }
    else {
        Write-Host "No matches found for '$SearchTerm'" -ForegroundColor Red
    }
    
    return $results
}

# Quick discovery function
function Start-QuickDiscovery {
    Write-Host "Starting quick RA area discovery..." -ForegroundColor Magenta
    Write-Host "This will test the first 100 area IDs using your Flask API." -ForegroundColor Yellow
    Write-Host ""
    
    $confirmation = Read-Host "Continue? This should take 2-3 minutes (Y/N)"
    
    if ($confirmation -eq 'Y' -or $confirmation -eq 'y') {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $outputPath = "ra_areas_quick_$timestamp.csv"
        
        $areas = Get-RAAreaCodes -StartId 1 -EndId 100 -BatchSize 10 -DelayMs 200 -OutputPath $outputPath
        
        Write-Host ""
        Write-Host "Quick discovery complete!" -ForegroundColor Magenta
        Write-Host "Use: Find-RAAreaByName -Areas `$areas -SearchTerm 'London'" -ForegroundColor Cyan
        
        return $areas
    }
    else {
        Write-Host "Discovery cancelled." -ForegroundColor Red
    }
}

# Comprehensive discovery function
function Start-FullDiscovery {
    Write-Host "Starting comprehensive RA area discovery..." -ForegroundColor Magenta
    Write-Host "This will test area IDs 1-2000 using your Flask API." -ForegroundColor Yellow
    Write-Host ""
    
    $confirmation = Read-Host "Continue? This may take 15-20 minutes (Y/N)"
    
    if ($confirmation -eq 'Y' -or $confirmation -eq 'y') {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $outputPath = "ra_areas_full_$timestamp.csv"
        
        $areas = Get-RAAreaCodes -StartId 1 -EndId 2000 -BatchSize 8 -DelayMs 400 -OutputPath $outputPath
        
        Write-Host ""
        Write-Host "Full discovery complete!" -ForegroundColor Magenta
        Write-Host "Use: Find-RAAreaByName -Areas `$areas -SearchTerm 'Germany'" -ForegroundColor Cyan
        
        return $areas
    }
    else {
        Write-Host "Discovery cancelled." -ForegroundColor Red
    }
}

# Auto-run when script is executed
Write-Host "RA Area Code Discovery Script (API Version) Loaded!" -ForegroundColor Magenta
Write-Host ""
Write-Host "IMPORTANT: Make sure your Flask API is running first!" -ForegroundColor Red
Write-Host "Run: python app.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "Available commands:" -ForegroundColor Yellow
Write-Host "  Get-RAAreaCodes -StartId 1 -EndId 100 -OutputPath 'areas.csv'" -ForegroundColor Cyan
Write-Host "  Start-QuickDiscovery" -ForegroundColor Cyan
Write-Host "  Start-FullDiscovery" -ForegroundColor Cyan
Write-Host "  Find-RAAreaByName -Areas `$areas -SearchTerm 'London'" -ForegroundColor Cyan
Write-Host ""

# Check if API is running
try {
    $healthCheck = Invoke-RestMethod -Uri "http://localhost:8080/" -Method Get -TimeoutSec 3
    Write-Host "Flask API is running at http://localhost:8080!" -ForegroundColor Green
    
    # Offer to run a quick test
    $runTest = Read-Host "Run a quick test discovery (IDs 1-20)? (Y/N)"
    if ($runTest -eq 'Y' -or $runTest -eq 'y') {
        Write-Host "Running quick test discovery..." -ForegroundColor Green
        $testAreas = Get-RAAreaCodes -StartId 1 -EndId 20 -BatchSize 5 -DelayMs 200 -OutputPath "ra_areas_test.csv"
        
        Write-Host ""
        Write-Host "Test complete! Found $($testAreas.Count) areas." -ForegroundColor Green
        Write-Host "Results saved to: ra_areas_test.csv" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "To run larger discoveries:" -ForegroundColor Yellow
        Write-Host "  Start-QuickDiscovery (100 areas)" -ForegroundColor Cyan
        Write-Host "  Start-FullDiscovery (2000 areas)" -ForegroundColor Cyan
    }
}
catch {
    Write-Host "Flask API not detected at http://localhost:8080" -ForegroundColor Red
    Write-Host "Start your API first with: python app.py" -ForegroundColor Yellow
    Write-Host "Then run this script again." -ForegroundColor Yellow
}