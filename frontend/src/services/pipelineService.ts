import { apiRequest } from "./api";

export interface Pipeline {
  pipeline_id: string;
  name: string;
  version: number;
}

export function listPipelines(): Promise<Pipeline[]> {
  return apiRequest<Pipeline[]>("/pipelines");
}
