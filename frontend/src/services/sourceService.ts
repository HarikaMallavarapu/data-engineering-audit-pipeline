import { apiRequest } from "./api";
import type { ApiPage } from "./api";

export interface SourceFile {
  source_file_id: string;
  original_filename: string;
  checksum: string;
  size_bytes: number;
  columns: string[];
  schema_fingerprint?: string | null;
  profile?: Record<string, unknown> | null;
  uploaded_at: string;
}

export function listSources(): Promise<ApiPage<SourceFile>> {
  return apiRequest<ApiPage<SourceFile>>("/sources");
}

export function uploadSource(file: File): Promise<SourceFile> {
  const body = new FormData();
  body.append("file", file);
  return apiRequest<SourceFile>("/sources/upload", { method: "POST", body });
}
