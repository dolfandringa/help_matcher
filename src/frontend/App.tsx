import { useEffect, useMemo, useRef } from "react";
import {
  Alert,
  AppBar,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Paper,
  Radio,
  RadioGroup,
  Select,
  Stack,
  TextField,
  Toolbar,
  Typography,
} from "@mui/material";
import FavoriteIcon from "@mui/icons-material/Favorite";
import MyLocationIcon from "@mui/icons-material/MyLocation";
import PhoneIcon from "@mui/icons-material/Phone";
import VolunteerActivismIcon from "@mui/icons-material/VolunteerActivism";
import type { StyleSpecification } from "maplibre-gl";
import Map, { Layer, Marker, NavigationControl, Source, type MapRef } from "react-map-gl/maplibre";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import { resultKey, useSearchStore } from "./store";
import { LocalWhatsAppPage } from "./LocalWhatsAppPage";
import type { AgeFilter, MapBounds, RecordType, SearchResult } from "./types";

const mapStyle: StyleSpecification = {
  version: 8,
  sources: {
    openstreetmap: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    {
      id: "openstreetmap",
      type: "raster",
      source: "openstreetmap",
    },
  ],
};

function recordTypeColor(recordType: RecordType) {
  return recordType === "demand" ? "#dc2626" : "#16a34a";
}

function resultLabel(result: SearchResult) {
  return result.record_type === "demand" ? "Need" : "Offer";
}

function resultLocation(result: SearchResult) {
  return (
    result.record.address_text ||
    result.record.administrative_area_name ||
    result.record.location_text ||
    "Location not specified"
  );
}

function recordTimestamp(result: SearchResult) {
  return result.record.updated_at || result.record.created_at;
}

function parseBackendUtcTimestamp(value: string) {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

function formatRelativeTime(value: string) {
  const timestamp = parseBackendUtcTimestamp(value).getTime();
  const diffSeconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (diffSeconds < 60) {
    return "just now";
  }
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  }
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function polygonFeatures(results: SearchResult[]): FeatureCollection {
  const features: Feature[] = results
    .filter((result) => result.record.geometry?.type === "Polygon")
    .map((result) => ({
      type: "Feature",
      geometry: result.record.geometry as Geometry,
      properties: {
        id: resultKey(result),
        color: recordTypeColor(result.record_type),
      },
    }));
  return { type: "FeatureCollection", features };
}

function longitudeInBounds(longitude: number, bounds: MapBounds) {
  if (bounds.west <= bounds.east) {
    return longitude >= bounds.west && longitude <= bounds.east;
  }
  return longitude >= bounds.west || longitude <= bounds.east;
}

function pointInBounds(coordinates: [number, number], bounds: MapBounds) {
  const [longitude, latitude] = coordinates;
  return longitudeInBounds(longitude, bounds) && latitude >= bounds.south && latitude <= bounds.north;
}

function resultInBounds(result: SearchResult, bounds?: MapBounds) {
  if (!bounds || !result.record.geometry) {
    return true;
  }
  if (result.record.geometry.type === "Point") {
    return pointInBounds(result.record.geometry.coordinates, bounds);
  }
  return result.record.geometry.coordinates.some((ring) =>
    ring.some((coordinates) => pointInBounds(coordinates, bounds)),
  );
}

function resultMatchesAgeFilter(result: SearchResult, ageFilter: AgeFilter) {
  if (ageFilter === "any") {
    return true;
  }
  const maxAgeMs = {
    "1h": 60 * 60 * 1000,
    "6h": 6 * 60 * 60 * 1000,
    "24h": 24 * 60 * 60 * 1000,
    "7d": 7 * 24 * 60 * 60 * 1000,
  }[ageFilter];
  return Date.now() - parseBackendUtcTimestamp(recordTimestamp(result)).getTime() <= maxAgeMs;
}

function useVisibleResults() {
  const results = useSearchStore((state) => state.results);
  const mapBounds = useSearchStore((state) => state.mapBounds);
  const ageFilter = useSearchStore((state) => state.ageFilter);
  return useMemo(
    () => results.filter((result) => resultInBounds(result, mapBounds) && resultMatchesAgeFilter(result, ageFilter)),
    [ageFilter, mapBounds, results],
  );
}

function SearchPanel() {
  const {
    ageFilter,
    query,
    recordTypes,
    isLoading,
    error,
    setAgeFilter,
    setQuery,
    setRecordTypes,
    loadDefaultRecords,
    search,
  } = useSearchStore();

  const selectType = (recordType: RecordType) => {
    const selectedTypes = [recordType];
    setRecordTypes(selectedTypes);
    if (query.trim().length === 0) {
      void loadDefaultRecords(selectedTypes);
    } else {
      void search(selectedTypes);
    }
  };

  const selectAgeFilter = (ageFilter: AgeFilter) => {
    setAgeFilter(ageFilter);
    if (query.trim().length === 0) {
      void loadDefaultRecords(recordTypes);
    } else {
      void search(recordTypes, ageFilter);
    }
  };

  return (
    <Paper className="search-panel" elevation={2}>
      <Stack spacing={2}>
        <Typography variant="h5" component="h1" fontWeight={700}>
          Find help nearby
        </Typography>
        <Box
          component="form"
          className="search-form"
          onSubmit={(event) => {
            event.preventDefault();
            void search();
          }}
        >
          <TextField
            fullWidth
            label="Search needs, offers, tags, or locations"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="water, tents, Chapinero..."
          />
          <Button type="submit" variant="contained" size="large" disabled={isLoading}>
            {isLoading ? <CircularProgress size={24} color="inherit" /> : "Search"}
          </Button>
        </Box>
        <RadioGroup
          row
          value={recordTypes[0]}
          onChange={(event) => selectType(event.target.value as RecordType)}
        >
          <FormControlLabel
            value="demand"
            control={<Radio />}
            label="Demands"
          />
          <FormControlLabel
            value="offer"
            control={<Radio />}
            label="Offers"
          />
        </RadioGroup>
        <FormControl fullWidth size="small">
          <InputLabel id="age-filter-label">Post age</InputLabel>
          <Select
            labelId="age-filter-label"
            label="Post age"
            value={ageFilter}
            onChange={(event) => selectAgeFilter(event.target.value as AgeFilter)}
          >
            <MenuItem value="any">Any time</MenuItem>
            <MenuItem value="1h">Last hour</MenuItem>
            <MenuItem value="6h">Last 6 hours</MenuItem>
            <MenuItem value="24h">Last 24 hours</MenuItem>
            <MenuItem value="7d">Last 7 days</MenuItem>
          </Select>
        </FormControl>
        {error ? <Alert severity="error">{error}</Alert> : null}
      </Stack>
    </Paper>
  );
}

function ResultsList() {
  const results = useVisibleResults();
  const { selectedResultId, setSelectedResultId } = useSearchStore();

  return (
    <Box className="results-list">
      {results.length === 0 ? (
        <Paper className="empty-state" variant="outlined">
          <Typography variant="h6">No open help needs found</Typography>
          <Typography color="text.secondary">
            Open demands appear by default. Select Offers to show open offers, or search to narrow results by tag, text, or location.
          </Typography>
        </Paper>
      ) : (
        results.map((result) => {
          const key = resultKey(result);
          const selected = selectedResultId === key;
          return (
            <Paper
              key={key}
              className={`result-card ${selected ? "selected" : ""}`}
              variant="outlined"
              onClick={() => setSelectedResultId(key)}
            >
              <Stack spacing={1}>
                <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1}>
                  <Chip
                    size="small"
                    label={resultLabel(result)}
                    sx={{ bgcolor: recordTypeColor(result.record_type), color: "white", fontWeight: 700 }}
                  />
                  <Chip size="small" variant="outlined" label={result.record.status} />
                </Stack>
                <Typography variant="subtitle1" fontWeight={700}>
                  {result.record.title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {resultLocation(result)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Updated {formatRelativeTime(recordTimestamp(result))}
                </Typography>
                {selected ? (
                  <>
                    <Typography variant="body2">{result.record.original_message}</Typography>
                    {result.record.contacts.length > 0 ? (
                      <Stack spacing={0.75}>
                        {result.record.contacts.map((contact) => (
                          <Box key={contact.id} className="contact-info selected">
                            <PhoneIcon fontSize="small" />
                            <Box>
                              <Typography variant="caption" color="text.secondary" display="block">
                                {contact.name || contact.username || "Contact"}
                              </Typography>
                              {contact.phone_number ? (
                                <Typography
                                  component="a"
                                  href={`tel:${contact.phone_number.replaceAll(" ", "")}`}
                                  variant="body2"
                                  fontWeight={700}
                                  color="inherit"
                                  onClick={(event) => event.stopPropagation()}
                                >
                                  {contact.phone_number}
                                </Typography>
                              ) : (
                                <Typography variant="body2" fontWeight={700}>
                                  No phone number
                                </Typography>
                              )}
                            </Box>
                          </Box>
                        ))}
                      </Stack>
                    ) : null}
                  </>
                ) : null}
                <Stack direction="row" flexWrap="wrap" gap={0.75}>
                  {result.record.tags.map((tag) => (
                    <Chip key={tag.id} size="small" label={tag.name} />
                  ))}
                </Stack>
              </Stack>
            </Paper>
          );
        })
      )}
    </Box>
  );
}

function ResultsMap() {
  const mapRef = useRef<MapRef>(null);
  const results = useVisibleResults();
  const { selectedResultId, userLocation, viewState, setViewState, setMapBounds, setSelectedResultId } = useSearchStore();
  const polygons = polygonFeatures(results);

  const updateMapBounds = () => {
    const bounds = mapRef.current?.getBounds();
    if (!bounds) {
      return;
    }
    setMapBounds({
      west: bounds.getWest(),
      south: bounds.getSouth(),
      east: bounds.getEast(),
      north: bounds.getNorth(),
    });
  };

  return (
    <Box className="map-panel">
      <Map
        ref={mapRef}
        {...viewState}
        onMove={(event) => setViewState(event.viewState)}
        onMoveEnd={updateMapBounds}
        onZoomEnd={updateMapBounds}
        onLoad={updateMapBounds}
        mapStyle={mapStyle}
        attributionControl={false}
      >
        <NavigationControl position="top-right" />
        {userLocation ? (
          <Marker longitude={userLocation.longitude} latitude={userLocation.latitude} anchor="center">
            <Box className="location-marker">
              <MyLocationIcon fontSize="small" />
            </Box>
          </Marker>
        ) : null}
        {polygons.features.length > 0 ? (
          <Source id="result-polygons" type="geojson" data={polygons}>
            <Layer
              id="result-polygons-fill"
              type="fill"
              paint={{ "fill-color": ["get", "color"], "fill-opacity": 0.22 }}
            />
            <Layer
              id="result-polygons-outline"
              type="line"
              paint={{ "line-color": ["get", "color"], "line-width": 2 }}
            />
          </Source>
        ) : null}
        {results
          .filter((result) => result.record.geometry?.type === "Point")
          .map((result) => {
            const key = resultKey(result);
            const point = result.record.geometry;
            if (!point || point.type !== "Point") {
              return null;
            }
            return (
              <Marker
                key={key}
                longitude={point.coordinates[0]}
                latitude={point.coordinates[1]}
                anchor="bottom"
                onClick={(event) => {
                  event.originalEvent.stopPropagation();
                  setSelectedResultId(key);
                }}
              >
                <Box
                  className={`map-marker ${selectedResultId === key ? "selected" : ""}`}
                  sx={{ bgcolor: recordTypeColor(result.record_type) }}
                >
                  {result.record_type === "demand" ? <FavoriteIcon fontSize="small" /> : <VolunteerActivismIcon fontSize="small" />}
                </Box>
              </Marker>
            );
          })}
      </Map>
    </Box>
  );
}

function SearchApp() {
  const useDeviceLocation = useSearchStore((state) => state.useDeviceLocation);
  const loadDefaultRecords = useSearchStore((state) => state.loadDefaultRecords);

  useEffect(() => {
    useDeviceLocation();
    void loadDefaultRecords();
  }, [loadDefaultRecords, useDeviceLocation]);

  return (
    <Box className="app-shell">
      <AppBar position="static" color="inherit" elevation={0}>
        <Toolbar>
          <Typography variant="h6" fontWeight={800}>
            Help Matcher
          </Typography>
        </Toolbar>
      </AppBar>
      <Box component="main" className="main-layout">
        <Box className="sidebar">
          <SearchPanel />
          <ResultsList />
        </Box>
        <ResultsMap />
      </Box>
    </Box>
  );
}

export function App() {
  return window.location.pathname === "/local-whatsapp" ? <LocalWhatsAppPage /> : <SearchApp />;
}
