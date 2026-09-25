export type Crop = { x: number; y: number; zoom: number };
export type SceneDecorationPosition = {
  top?: string;
  right?: string;
  bottom?: string;
  left?: string;
};
export type SceneDecorationNote = {
  text: string;
  rotate?: number;
  position?: SceneDecorationPosition;
  opacity?: number;
  color?: string;
  fontStyle?: "ui" | "handwritten";
  maxWidth?: string;
};
export type SceneSpaceEntry = {
  text: string;
  icon: "Images" | "Heart" | "Sparkles";
  iconPosition?: "start" | "end";
  action: "album" | "history" | "profile";
  offsetX?: number;
  dividerWidth?: number;
};
export type SceneDecorations = {
  homeGreeting?: string;
  avatarNote?: { text: string; opacity?: number; color?: string };
  spaceColor?: string;
  leftMenu?: SceneSpaceEntry[];
  signature?: SceneDecorationNote & { indent?: number };
  topNote?: SceneDecorationNote;
  bottomNote?: SceneDecorationNote;
};
export type Character = {
  id: string;
  name: string;
  romanized: string;
  world: string;
  versionId: string;
  cover: string;
  sceneBackground?: string;
  sceneBackgroundPosition?: string;
  sceneDecorations?: SceneDecorations;
  description: string;
  tagline?: string;
  tags?: string[];
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
export type Memory = {
  memory_id: string;
  instance_id: string;
  kind: "fact" | "inference";
  memory_type: "fact" | "preference" | "event";
  content: string;
  status: "active";
  revision: number;
  created_at: string;
  updated_at: string;
  source: null | {
    message_id: string;
    turn_id: string;
    conversation_id: string;
    role: "user";
  };
};
export type MemoryPage = {
  items: Memory[];
  total: number;
  offset: number;
  limit: number;
};
export type Matter = {
  matter_id: string;
  revision: number;
  matter_type: "reminder" | "commitment" | "follow_up";
  status: "open" | "completed" | "cancelled";
  content: string;
  next_step: string | null;
  time_precision: "instant" | "day" | "month" | "unknown";
  scheduled_at: string | null;
  timezone_name: string | null;
  mention_policy: "when_relevant" | "on_due" | "never";
};
export type MatterPage = { items: Matter[] };
export type ReminderDelivery = {
  delivery_id: string;
  lease_token: string;
  occurrence_key: string;
  matter_id: string;
  content: string;
  due_at: string;
  timezone_name: string;
};
