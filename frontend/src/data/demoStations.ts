import type { MapStation, VehicleClass } from '../types/station'

// Synthetic example locations for UI development. These are not verified
// station listings or official infrastructure records.
export const demoStations: MapStation[] = [
  { id: 'DEMO-KA-001', name: 'Bengaluru Central Example', latitude: 12.9716, longitude: 77.5946, state: 'Karnataka', district: 'Bengaluru Urban', chargerType: 'DC fast', source: 'Illustrative demo dataset', isDemo: true, confidence: 0.94, supportedVehicleClasses: ['2W', '3W', '4W'] },
  { id: 'DEMO-KA-002', name: 'Whitefield Example Point', latitude: 12.9698, longitude: 77.75, state: 'Karnataka', district: 'Bengaluru Urban', chargerType: 'AC', source: 'Illustrative demo dataset', isDemo: true, confidence: 0.81, supportedVehicleClasses: ['2W', '4W'] },
  { id: 'DEMO-KA-003', name: 'Electronic City Example', latitude: 12.8452, longitude: 77.6602, state: 'Karnataka', district: 'Bengaluru Urban', chargerType: 'DC fast', source: 'Illustrative demo dataset', isDemo: true, confidence: 0.67, supportedVehicleClasses: ['3W', '4W'] },
  { id: 'DEMO-KA-004', name: 'Mysuru Example Station', latitude: 12.2958, longitude: 76.6394, state: 'Karnataka', district: 'Mysuru', chargerType: 'AC', source: 'Illustrative demo dataset', isDemo: true, supportedVehicleClasses: null },
  { id: 'DEMO-KA-005', name: 'Hubballi Example Station', latitude: 15.3647, longitude: 75.124, state: 'Karnataka', district: 'Dharwad', chargerType: 'DC fast', source: 'Illustrative demo dataset', isDemo: true, confidence: 0.76, supportedVehicleClasses: ['2W', '3W'] },
  { id: 'DEMO-MH-001', name: 'Pune Central Example', latitude: 18.5204, longitude: 73.8567, state: 'Maharashtra', district: 'Pune', chargerType: 'DC fast', source: 'Illustrative demo dataset', isDemo: true, confidence: 0.91, supportedVehicleClasses: ['2W', '3W', '4W'] },
  { id: 'DEMO-MH-002', name: 'Hinjawadi Example Point', latitude: 18.5913, longitude: 73.7389, state: 'Maharashtra', district: 'Pune', chargerType: 'AC', source: 'Illustrative demo dataset', isDemo: true, confidence: 0.73, supportedVehicleClasses: ['2W', '4W'] },
  { id: 'DEMO-MH-003', name: 'Nagpur Example Station', latitude: 21.1458, longitude: 79.0882, state: 'Maharashtra', district: 'Nagpur', chargerType: 'DC fast', source: 'Illustrative demo dataset', isDemo: true, confidence: 0.58, supportedVehicleClasses: ['3W', '4W'] },
  { id: 'DEMO-MH-004', name: 'Nashik Example Point', latitude: 19.9975, longitude: 73.7898, state: 'Maharashtra', district: 'Nashik', chargerType: 'AC', source: 'Illustrative demo dataset', isDemo: true, supportedVehicleClasses: null },
  { id: 'DEMO-MH-005', name: 'Mumbai Example Station', latitude: 19.076, longitude: 72.8777, state: 'Maharashtra', district: 'Mumbai Suburban', chargerType: 'DC fast', source: 'Illustrative demo dataset', isDemo: true, confidence: 0.88, supportedVehicleClasses: ['2W', '3W', '4W'] },
  { id: 'DEMO-DL-001', name: 'New Delhi Example Point', latitude: 28.6139, longitude: 77.209, state: 'Delhi', district: 'New Delhi', chargerType: 'DC fast', source: 'Illustrative demo dataset', isDemo: true, confidence: 0.86, supportedVehicleClasses: ['2W', '4W'] },
  { id: 'DEMO-TN-001', name: 'Chennai Example Station', latitude: 13.0827, longitude: 80.2707, state: 'Tamil Nadu', district: 'Chennai', chargerType: 'AC', source: 'Illustrative demo dataset', isDemo: true, supportedVehicleClasses: null },
  { id: 'DEMO-TG-001', name: 'Hyderabad Example Station', latitude: 17.385, longitude: 78.4867, state: 'Telangana', district: 'Hyderabad', chargerType: 'DC fast', source: 'Illustrative demo dataset', isDemo: true, confidence: 0.79, supportedVehicleClasses: ['2W', '3W', '4W'] },
  { id: 'DEMO-WB-001', name: 'Kolkata Example Point', latitude: 22.5726, longitude: 88.3639, state: 'West Bengal', district: 'Kolkata', chargerType: 'AC', source: 'Illustrative demo dataset', isDemo: true, confidence: 0.62, supportedVehicleClasses: ['2W', '3W'] },
]

export const demoStates = ['Delhi', 'Karnataka', 'Maharashtra', 'Tamil Nadu', 'Telangana', 'West Bengal']
