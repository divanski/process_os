<?php

namespace App\Http\Controllers;

class ShipmentController
{
    public function index()
    {
        return ['shipments' => []];
    }

    public function track(string $trackingNumber)
    {
        return ['tracking_number' => $trackingNumber, 'status' => 'unknown'];
    }
}
