<?php

return [
    /*
    |--------------------------------------------------------------------------
    | {ServiceName} Default Driver
    |--------------------------------------------------------------------------
    |
    | This option controls the default "{ServiceName}" driver that will be used by the
    | framework when using the {ServiceName} features.
    |
    */

    'default' => env('{SERVICE_NAME_UPPER}_DRIVER', '{DefaultDriver}'),

    /*
    |--------------------------------------------------------------------------
    | {ServiceName} Drivers
    |--------------------------------------------------------------------------
    |
    | Here are each of the {ServiceName} drivers setup for your application.
    |
    */

    'drivers' => [
{Drivers}
    ],

    /*
    |--------------------------------------------------------------------------
    | {ServiceName} Configuration
    |--------------------------------------------------------------------------
    |
    | Configuration options for {ServiceName} service.
    |
    */

    'options' => [
        // Add service-specific configuration here
    ],
];
