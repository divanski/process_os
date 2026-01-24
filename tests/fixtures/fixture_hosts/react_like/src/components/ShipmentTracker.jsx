import React, { useState } from 'react';

export function ShipmentTracker() {
  const [trackingNumber, setTrackingNumber] = useState('');
  const [status, setStatus] = useState(null);

  const handleTrack = async () => {
    // Placeholder for tracking API
    setStatus({ trackingNumber, status: 'pending' });
  };

  return (
    <div className="shipment-tracker">
      <input
        type="text"
        value={trackingNumber}
        onChange={(e) => setTrackingNumber(e.target.value)}
        placeholder="Enter tracking number"
      />
      <button onClick={handleTrack}>Track</button>
      {status && (
        <div className="status">
          <p>Tracking: {status.trackingNumber}</p>
          <p>Status: {status.status}</p>
        </div>
      )}
    </div>
  );
}
