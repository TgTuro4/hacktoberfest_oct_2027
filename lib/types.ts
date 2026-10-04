export type ItemKind = "group" | "event";
export type Decision = "interested" | "pass";

export interface Draft {
  kind: ItemKind;
  title: string;
  description: string;
  tags: string[];
  location: string;
  date: string;
  time: string;
  meetingDetails: string;
}

export interface CampusItem extends Draft {
  id: string;
  demo: boolean;
  color: number;
  createdAt: string;
  isActive?: boolean;
  startsAt?: string;
  sourceUrl?: string;
  allDay?: boolean;
}

export interface Profile {
  name: string;
  major: string;
  bio: string;
  interests: string[];
  availability: string;
}

export interface DemoState {
  version: 1;
  items: CampusItem[];
  profile: Profile;
  decisions: Record<string, Decision>;
}

export interface PrefillDraft extends Draft {
  reviewNotes: string[];
}

export interface PrefillResult {
  source: "sample" | "snowflake";
  message: string;
  drafts: PrefillDraft[];
}

export const emptyDraft = (kind: ItemKind = "event"): Draft => ({
  kind, title: "", description: "", tags: [], location: "", date: "", time: "", meetingDetails: "",
});
