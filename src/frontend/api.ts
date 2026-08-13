import type { HelpRecord, RecordType, SearchResult } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function searchHelpRecords(query: string, recordTypes: RecordType[]): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q: query });
  recordTypes.forEach((recordType) => params.append("record_type", recordType));

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
