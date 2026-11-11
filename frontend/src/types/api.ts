export type ProcessingStatus = "draft" | "uploaded" | "transcribing" | "analyzing" | "ready" | "failed";
export type ActionStatus = "todo" | "in_progress" | "done";
export type TeamRole = "owner" | "admin" | "member";
export type SaveStatus = "idle" | "saving" | "saved" | "error";

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    request_id: string;
    details?: Record<string, unknown>;
  };
}

export interface User {
  id: string;
  name: string;
  email: string;
  avatar_color?: string;
  avatar_url?: string | null;
}

export interface TeamMember extends User {
  role: TeamRole;
}

export interface Team {
  id: string;
  name: string;
  description: string;
  member_count: number;
  my_role: TeamRole;
  created_at?: string;
}

export interface TeamDetail extends Team {
  members: TeamMember[];
}

export interface DiscussionItem {
  id: string;
  text: string;
  evidence?: string;
}

export interface ActionItem {
  id: string;
  description: string;
  assignee_id: string | null;
  assignee_name: string | null;
  due_date: string | null;
  status: ActionStatus;
}

export interface Meeting {
  id: string;
  team_id: string;
  title: string;
  meeting_at: string;
  created_by: User;
  processing_status: ProcessingStatus;
  is_mine: boolean;
  is_shared_with_me: boolean;
  summary: string;
  transcript_original: string;
  transcript_edited: string;
  key_discussions: DiscussionItem[];
  decisions: DiscussionItem[];
  follow_ups: DiscussionItem[];
  action_items: ActionItem[];
  shared_member_ids: string[];
  ai_generated_at: string | null;
  version: number;
}

export interface ProcessingJob {
  id: string;
  meeting_id: string;
  job_type: "analyze";
  status: "queued" | "processing" | "succeeded" | "failed";
  attempt_count: number;
  error_code: string | null;
  error_message: string | null;
  retryable: boolean;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface MockSession {
  user: User;
  is_mock: true;
}

export interface ProcessingStep {
  id: string;
  label: string;
  state: "pending" | "active" | "complete" | "failed";
}
