-- İsteğe bağlı PostGIS şeması. Yönetilen PostgreSQL üzerinde yetkili kullanıcı tarafından çalıştırılır.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS public.parcel_geometries (
    id BIGSERIAL PRIMARY KEY,
    province TEXT NOT NULL,
    district TEXT NOT NULL,
    neighborhood TEXT NOT NULL,
    block_no TEXT NOT NULL,
    parcel_no TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    license_note TEXT,
    geom geometry(MultiPolygon, 4326) NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS parcel_geometries_geom_gix
ON public.parcel_geometries USING GIST (geom);

CREATE INDEX IF NOT EXISTS parcel_geometries_lookup_idx
ON public.parcel_geometries (province, district, neighborhood, block_no, parcel_no);
