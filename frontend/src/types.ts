export type Crop = { x: number; y: number; zoom: number };
export type Character = {
  id: string;
  name: string;
  romanized: string;
  world: string;
  versionId: string;
  cover: string;
  description: string;
  dataStatus: string;
  checkpointLabel: string;
  theme: Record<string, string>;
  crop: { chat: Crop; selection: Crop };
  sendControl: { label: string; image: string | null };
  default?: boolean;
};
export type Cover = { source: string; crop: Character["crop"] };
export type Turn = {
  turn_id: string;
  request_id: string;
  sequence: number;
  status: string;
  error_code: string | null;
  created_at: string | null;
  messages: { message_id: string; role: string; text: string }[];
};
export type History = { total: number; offset: number; turns: Turn[] };
export type Session = {
  conversation_id: string;
  instance_id: string;
  character_id: string;
  name: string;
  version_id: string;
  checkpoint: string;
  created_at: string | null;
  last_activity_at: string | null;
  preview: string;
  turns: number;
};
export type SessionPage = {
  items: Session[];
  total: number;
  offset: number;
  limit: number;
};
