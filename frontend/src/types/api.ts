export type ProcessingStatus = "draft" | "uploaded" | "transcribing" | "analyzing" | "ready" | "failed";
export type ActionStatus = "todo" | "in_progress" | "done";
export type TeamRole = "owner" | "admin" | "member";
export type OrganizationRole = "org_admin" | "member";
export type DepartmentRole = "department_admin" | "member";
export type SaveStatus = "idle" | "saving" | "saved" | "error";
export type MeetingType = "general" | "project" | "interview" | "workshop";

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
  organization: TeamScope | null;
  department: TeamScope | null;
}

export interface TeamScope {
  id: string;
  name: string;
}

export interface Department {
  id: string;
  organization_id: string;
  name: string;
  description: string;
  my_role: DepartmentRole | null;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  description: string;
  my_role: OrganizationRole;
  created_at: string;
}

export interface OrganizationDetail extends Organization {
  departments: Department[];
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
  review_status: "draft" | "review_required" | "approved" | "rejected";
  approved_at: string | null;
  approved_by: string | null;
  approval_version: number | null;
  is_mine: boolean;
  is_shared_with_me: boolean;
  summary: string;
  transcript_original: string;
  transcript_edited: string;
  transcript_speakers: TranscriptSpeaker[];
  transcript_segments: TranscriptSegment[];
  key_discussions: DiscussionItem[];
  decisions: DiscussionItem[];
  follow_ups: DiscussionItem[];
  action_items: ActionItem[];
  shared_member_ids: string[];
  ai_generated_at: string | null;
  version: number;
  topic: string;
  location: string;
  meeting_type: MeetingType;
  purpose: string;
  project_name: string;
  template_id: string | null;
  metadata_confirmed_at: string | null;
  attendees: MeetingAttendee[];
  transcript_corrected: string;
  questions: MeetingQuestion[];
  latest_speaker_edit_batch_id: string | null;
}

export type MeetingListItem = Pick<
  Meeting,
  | "id"
  | "team_id"
  | "title"
  | "meeting_at"
  | "created_by"
  | "processing_status"
  | "is_mine"
  | "is_shared_with_me"
  | "version"
>;

export interface TranscriptSpeaker {
  id: string;
  provider_label: string;
  display_name: string;
  candidate_user_id?: string | null;
  candidate_confidence?: number | null;
  candidate_reason?: string;
  confirmed_at?: string | null;
}

export interface TranscriptSegment {
  id: string;
  speaker_id: string;
  speaker_name: string;
  start_seconds: number;
  end_seconds: number;
  text: string;
  original_speaker_id: string | null;
}

export interface MeetingAttendee {
  id: string;
  user_id: string | null;
  external_name: string | null;
  external_organization: string | null;
  display_name: string;
}

export interface TemplateSection {
  key: string;
  label: string;
}

export interface MeetingTemplate {
  id: string;
  organization_id: string | null;
  department_id: string | null;
  team_id: string | null;
  name: string;
  description: string;
  meeting_type: MeetingType;
  sections: TemplateSection[];
  writing_rules: string;
  is_default: boolean;
  version: number;
  is_active: boolean;
  is_builtin: boolean;
  created_at: string | null;
}

export interface GlossaryTerm {
  id: string;
  organization_id: string | null;
  department_id: string | null;
  team_id: string | null;
  term: string;
  preferred_term: string;
  aliases: string[];
  description: string;
  created_at: string;
}

export interface QualityOptions {
  templates: MeetingTemplate[];
  glossary_terms: GlossaryTerm[];
}

export interface MeetingQuestion {
  id: string;
  category: "decision" | "assignee" | "due_date" | "number" | "name" | "speaker" | "other";
  question: string;
  evidence: string | null;
  answer: string | null;
  status: "pending" | "answered" | "dismissed";
  created_at: string;
  answered_at: string | null;
}

export interface TranscriptCorrectionResult {
  corrected_text: string;
  changes: Array<{ original: string; corrected: string; reason: string }>;
  uncertainties: Array<{ category: MeetingQuestion["category"]; question: string; evidence: string | null }>;
}

export interface ProcessingJob {
  id: string;
  meeting_id: string;
  job_type: "extract" | "transcribe" | "analyze";
  status: "queued" | "processing" | "succeeded" | "failed";
  attempt_count: number;
  error_code: string | null;
  error_message: string | null;
  retryable: boolean;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  requested_provider: "openai" | "whisperx" | null;
  worker_online: boolean | null;
}

export type FileProcessingStatus = "pending_upload" | "uploaded" | "processing" | "succeeded" | "failed";

export interface MeetingFile {
  id: string;
  meeting_id: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  processing_status: FileProcessingStatus;
  error_code: string | null;
  created_at: string;
  requested_stt_provider: "openai" | "whisperx";
}

export interface UploadUrlResponse {
  file: MeetingFile;
  bucket: string;
  path: string;
  token: string;
  signed_url: string;
}

export interface FileCompleteResponse {
  file: MeetingFile;
  job_id: string;
  job_type: "extract" | "transcribe";
  requested_provider: "openai" | "whisperx" | null;
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
