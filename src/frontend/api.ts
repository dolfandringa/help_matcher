import type { AgeFilter, HelpRecord, RecordType, SearchResult } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export function updatedSinceForAgeFilter(ageFilter: AgeFilter): string | undefined {
  const maxAgeMs = {
    any: undefined,
    "1h": 60 * 60 * 1000,
    "6h": 6 * 60 * 60 * 1000,
    "24h": 24 * 60 * 60 * 1000,
    "7d": 7 * 24 * 60 * 60 * 1000,
  }[ageFilter];
  return maxAgeMs === undefined ? undefined : new Date(Date.now() - maxAgeMs).toISOString().replace("Z", "");
}

export async function searchHelpRecords(
  query: string,
  recordTypes: RecordType[],
  ageFilter: AgeFilter,
): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q: query });
  recordTypes.forEach((recordType) => params.append("record_type", recordType));
  const updatedSince = updatedSinceForAgeFilter(ageFilter);
  if (updatedSince) {
    params.set("updated_since", updatedSince);
  }

  const response = await fetch(`${API_BASE_URL}/search?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Search failed with status ${response.status}`);
  }
  return response.json();
}

export async function listOpenDemands(): Promise<SearchResult[]> {
  const response = await fetch(`${API_BASE_URL}/demands?status=open`);
  if (!response.ok) {
    throw new Error(`Loading help needs failed with status ${response.status}`);
  }
  const demands = (await response.json()) as HelpRecord[];
  return demands.map((record) => ({ record_type: "demand", record }));
}

export async function listOpenOffers(): Promise<SearchResult[]> {
  const response = await fetch(`${API_BASE_URL}/offers?status=open`);
  if (!response.ok) {
    throw new Error(`Loading offers failed with status ${response.status}`);
  }
  const offers = (await response.json()) as HelpRecord[];
  return offers.map((record) => ({ record_type: "offer", record }));
}

export async function listOpenRecords(recordTypes: RecordType[]): Promise<SearchResult[]> {
  const results = await Promise.all([
    recordTypes.includes("demand") ? listOpenDemands() : Promise.resolve([]),
    recordTypes.includes("offer") ? listOpenOffers() : Promise.resolve([]),
  ]);
  return results.flat();
}
