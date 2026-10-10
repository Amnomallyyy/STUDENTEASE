// The three cities the seeded job dataset covers (data/jobs.json). Picking a city uses its centre;
// "Use my location" uses the browser Geolocation API instead.
export interface City {
  name: string;
  lat: number;
  lng: number;
}

export const CITIES: City[] = [
  { name: "Karachi", lat: 24.8607, lng: 67.0011 },
  { name: "Lahore", lat: 31.5204, lng: 74.3587 },
  { name: "Islamabad", lat: 33.6844, lng: 73.0479 },
];

export function findCity(name: string): City | undefined {
  const key = name.trim().toLowerCase();
  return CITIES.find((c) => c.name.toLowerCase() === key);
}
