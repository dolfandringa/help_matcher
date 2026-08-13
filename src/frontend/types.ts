export type RecordType = "offer" | "demand";
export type AgeFilter = "any" | "1h" | "6h" | "24h" | "7d";

export type GeoJsonPoint = {
  type: "Point";
  coordinates: [number, number];
};

export type GeoJsonPolygon = {
  type: "Polygon";
  coordinates: [number, number][][];
};

export type HelpRecord = {
  id: number;
  title: string;
  original_message: string;
  location_text?: string | null;
  administrative_area_name?: string | null;
  administrative_area_level?: string | null;
  address_text?: string | null;
  status: "open" | "closed";
  geometry?: GeoJsonPoint | GeoJsonPolygon | null;
  contacts: {
    id: number;
    name?: string | null;
    username?: string | null;
    phone_number?: string | null;
    whatsapp_bsuid?: string | null;
  }[];
  tags: { id: number; name: string; description?: string | null }[];
  created_at: string;
  updated_at: string;
  closed_at?: string | null;
};

export type SearchResult = {
  record_type: RecordType;
  record: HelpRecord;
};

export type ViewState = {
  longitude: number;
  latitude: number;
  zoom: number;
};

export type MapBounds = {
  west: number;
  south: number;
  east: number;
  north: number;
};
