import { create } from "zustand";
import { listOpenRecords, searchHelpRecords } from "./api";
import type { AgeFilter, MapBounds, RecordType, SearchResult, ViewState } from "./types";

type SearchState = {
  query: string;
  recordTypes: RecordType[];
  ageFilter: AgeFilter;
  results: SearchResult[];
  selectedResultId?: string;
  viewState: ViewState;
  mapBounds?: MapBounds;
  userLocation?: { longitude: number; latitude: number };
  isLoading: boolean;
  error?: string;
  setQuery: (query: string) => void;
  setAgeFilter: (ageFilter: AgeFilter) => void;
  setRecordTypes: (recordTypes: RecordType[]) => void;
  setSelectedResultId: (id?: string) => void;
  setViewState: (viewState: ViewState) => void;
  setMapBounds: (mapBounds: MapBounds) => void;
  useDeviceLocation: () => void;
  loadDefaultRecords: (recordTypes?: RecordType[]) => Promise<void>;
  search: (recordTypesOverride?: RecordType[], ageFilterOverride?: AgeFilter) => Promise<void>;
};

const colombiaView: ViewState = {
  longitude: -74.2973,
  latitude: 4.5709,
  zoom: 5,
};

export const resultKey = (result: SearchResult) => `${result.record_type}-${result.record.id}`;

export const useSearchStore = create<SearchState>((set, get) => ({
  query: "",
  recordTypes: ["demand"],
  ageFilter: "any",
  results: [],
  viewState: colombiaView,
  isLoading: false,
  setQuery: (query) => set({ query }),
  setAgeFilter: (ageFilter) => set({ ageFilter }),
  setRecordTypes: (recordTypes) => set({ recordTypes }),
  setSelectedResultId: (selectedResultId) => set({ selectedResultId }),
  setViewState: (viewState) => set({ viewState }),
  setMapBounds: (mapBounds) => set({ mapBounds }),
  useDeviceLocation: () => {
    if (!navigator.geolocation) {
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const userLocation = {
          longitude: position.coords.longitude,
          latitude: position.coords.latitude,
        };
        set({
          userLocation,
          viewState: {
            ...userLocation,
            zoom: 14,
          },
        });
      },
      () => undefined,
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 },
    );
  },
  loadDefaultRecords: async (recordTypesOverride) => {
    const recordTypes = recordTypesOverride ?? get().recordTypes;
    set({ isLoading: true, error: undefined });
    try {
      const results = await listOpenRecords(recordTypes);
      set({ results, isLoading: false, selectedResultId: results[0] ? resultKey(results[0]) : undefined });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : "Loading records failed",
      });
    }
  },
  search: async (recordTypesOverride, ageFilterOverride) => {
    const { ageFilter, query, recordTypes, loadDefaultRecords } = get();
    const selectedRecordTypes = recordTypesOverride ?? recordTypes;
    const selectedAgeFilter = ageFilterOverride ?? ageFilter;
    if (query.trim().length === 0) {
      await loadDefaultRecords(selectedRecordTypes);
      return;
    }

    set({ isLoading: true, error: undefined });
    try {
      const results = await searchHelpRecords(query.trim(), selectedRecordTypes, selectedAgeFilter);
      set({ results, isLoading: false, selectedResultId: results[0] ? resultKey(results[0]) : undefined });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : "Search failed",
      });
    }
  },
}));
