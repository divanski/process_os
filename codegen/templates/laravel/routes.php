<?php

use Illuminate\Support\Facades\Route;
use {ControllerNamespace}\{ControllerClass};

Route::middleware('api')->prefix('api')->group(function () {
    Route::prefix('{ServiceName}')->group(function () {
        // {ServiceName} endpoints
{Routes}
    });
});
