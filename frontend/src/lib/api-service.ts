import { sha256 } from "@noble/hashes/sha256";
import * as tus from "tus-js-client";

import { apiRequest } from "@/lib/api-client";
import { supabase } from "@/lib/supabase";
import type { Department, FileCompleteResponse, GlossaryTerm, Meeting, MeetingFile, MeetingListItem, MeetingQuestion, MeetingTemplate, Organization, OrganizationDetail, ProcessingJob, QualityOptions, Team, TeamDetail, TeamMember, TranscriptCorrectionResult, UploadUrlResponse, User } from "@/types/api";

interface MeApiResponse {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
}

const avatarColors = ["bg-indigo-500", "bg-violet-500", "bg-emerald-500", "bg-sky-500"];
const avatarColor = (id: string) => avatarColors[id.charCodeAt(id.length - 1) % avatarColors.length];

function normalizeUser(user: User): User {
  return { ...user, avatar_color: user.avatar_color ?? avatarColor(user.id) };
}

function normalizeMeeting(meeting: Meeting): Meeting {
  return { ...meeting, created_by: normalizeUser(meeting.created_by) };
}

function normalizeMeetingListItem(meeting: MeetingListItem): MeetingListItem {
  return { ...meeting, created_by: normalizeUser(meeting.created_by) };
}

function normalizeMember(member: TeamMember): TeamMember {
  return { ...member, avatar_color: member.avatar_color ?? avatarColor(member.id) };
}

export const apiService = {
  async getMe(): Promise<User> {
    const me = await apiRequest<MeApiResponse>("/api/v1/me");
    return normalizeUser({ id: me.id, name: me.display_name, email: me.email, avatar_url: me.avatar_url });
  },
  getTeams: () => apiRequest<Team[]>("/api/v1/teams"),
  createTeam: (input: { name: string; organization_id?: string; department_id?: string }) => apiRequest<Team>("/api/v1/teams", { method: "POST", body: JSON.stringify(input) }),
  getOrganizations: () => apiRequest<Organization[]>("/api/v1/organizations"),
  createOrganization: (name: string) => apiRequest<Organization>("/api/v1/organizations", { method: "POST", body: JSON.stringify({ name }) }),
  getOrganization: (id: string) => apiRequest<OrganizationDetail>(`/api/v1/organizations/${id}`),
  createDepartment: (organizationId: string, name: string) => apiRequest<Department>(`/api/v1/organizations/${organizationId}/departments`, { method: "POST", body: JSON.stringify({ name }) }),
  async getTeam(teamId: string): Promise<TeamDetail> {
    const team = await apiRequest<TeamDetail>(`/api/v1/teams/${teamId}`);
    return { ...team, members: team.members.map(normalizeMember) };
  },
  async getMeetings(teamId: string): Promise<MeetingListItem[]> {
    const meetings = await apiRequest<MeetingListItem[]>(`/api/v1/meetings?team_id=${encodeURIComponent(teamId)}`);
    return meetings.map(normalizeMeetingListItem);
  },
  async getMeeting(id: string): Promise<Meeting> {
    return normalizeMeeting(await apiRequest<Meeting>(`/api/v1/meetings/${id}`));
  },
  async createMeeting(input: { team_id: string; title: string; meeting_at: string; source_type?: "direct" | "txt" | "pdf" | "audio"; topic?: string; location?: string; meeting_type?: "general" | "project" | "interview" | "workshop"; purpose?: string; project_name?: string; template_id?: string | null; attendees?: Array<{ user_id?: string; external_name?: string; external_organization?: string }>; metadata_confirmed?: boolean }): Promise<Meeting> {
    return normalizeMeeting(await apiRequest<Meeting>("/api/v1/meetings", {
      method: "POST",
      body: JSON.stringify({ ...input, source_type: input.source_type ?? "direct" }),
    }));
  },
  async updateMeeting(id: string, input: { title?: string; meeting_at?: string; version: number; topic?: string; location?: string; meeting_type?: "general" | "project" | "interview" | "workshop"; purpose?: string; project_name?: string; template_id?: string | null; attendees?: Array<{ user_id?: string; external_name?: string; external_organization?: string }>; metadata_confirmed?: boolean }): Promise<Meeting> {
    return normalizeMeeting(await apiRequest<Meeting>(`/api/v1/meetings/${id}`, { method: "PATCH", body: JSON.stringify(input) }));
  },
  async saveTranscript(id: string, text: string): Promise<Meeting> {
    return normalizeMeeting(await apiRequest<Meeting>(`/api/v1/meetings/${id}/transcript`, { method: "POST", body: JSON.stringify({ text }) }));
  },
  async updateTranscriptSpeaker(
    meetingId: string,
    speakerId: string,
    displayName: string,
  ): Promise<Meeting> {
    return normalizeMeeting(
      await apiRequest<Meeting>(
        `/api/v1/meetings/${meetingId}/transcript/speakers/${speakerId}`,
        {
          method: "PATCH",
          body: JSON.stringify({ display_name: displayName }),
        },
      ),
    );
  },
  async updateNotes(id: string, input: {
    summary: string;
    key_discussions: Array<{ id: string; text: string; evidence?: string }>;
    decisions: Array<{ id: string; text: string; evidence?: string }>;
    follow_ups: Array<{ id: string; text: string; evidence?: string }>;
    version: number;
  }): Promise<Meeting> {
    return normalizeMeeting(await apiRequest<Meeting>(`/api/v1/meetings/${id}/notes`, {
      method: "PATCH",
      body: JSON.stringify(input),
    }));
  },
  deleteMeeting: (id: string) => apiRequest<void>(`/api/v1/meetings/${id}`, { method: "DELETE" }),
  startAnalysis: (id: string) => apiRequest<ProcessingJob>(`/api/v1/meetings/${id}/process`, { method: "POST" }),
  getJob: (id: string) => apiRequest<ProcessingJob>(`/api/v1/jobs/${id}`),
  retryJob: (id: string) => apiRequest<ProcessingJob>(`/api/v1/jobs/${id}/retry`, { method: "POST" }),
  createUploadUrl: (meetingId: string, input: { filename: string; content_type: string; size_bytes: number; sha256: string }) =>
    apiRequest<UploadUrlResponse>(`/api/v1/meetings/${meetingId}/files/upload-url`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  async uploadFile(input: UploadUrlResponse, file: File): Promise<void> {
    if (!supabase) throw new Error("파일 업로드 설정을 확인해 주세요.");
    if (file.size > 6 * 1024 * 1024) {
      await uploadResumable(input, file);
      return;
    }
    const { error } = await supabase.storage
      .from(input.bucket)
      .uploadToSignedUrl(input.path, input.token, file, {
        contentType: input.file.mime_type,
        upsert: false,
      });
    if (error) throw new Error("파일을 업로드하지 못했어요. 다시 시도해 주세요.");
  },
  completeUpload: (meetingId: string, fileId: string) =>
    apiRequest<FileCompleteResponse>(`/api/v1/meetings/${meetingId}/files/${fileId}/complete`, {
      method: "POST",
    }),
  getMeetingFiles: (meetingId: string) =>
    apiRequest<MeetingFile[]>(`/api/v1/meetings/${meetingId}/files`),
  getQualityOptions: (teamId: string) =>
    apiRequest<QualityOptions>(`/api/v1/teams/${teamId}/quality-options`),
  createTemplate: (input: Omit<MeetingTemplate, "id" | "version" | "is_active" | "is_builtin" | "created_at">) =>
    apiRequest<MeetingTemplate>("/api/v1/meeting-templates", { method: "POST", body: JSON.stringify(input) }),
  updateTemplate: (id: string, input: Partial<Pick<MeetingTemplate, "name" | "description" | "sections" | "writing_rules" | "is_default" | "is_active">>) =>
    apiRequest<MeetingTemplate>(`/api/v1/meeting-templates/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  deleteTemplate: (id: string) => apiRequest<void>(`/api/v1/meeting-templates/${id}`, { method: "DELETE" }),
  createGlossaryTerm: (input: Omit<GlossaryTerm, "id" | "created_at">) =>
    apiRequest<GlossaryTerm>("/api/v1/glossary-terms", { method: "POST", body: JSON.stringify(input) }),
  updateGlossaryTerm: (id: string, input: Partial<Pick<GlossaryTerm, "term" | "preferred_term" | "aliases" | "description">>) =>
    apiRequest<GlossaryTerm>(`/api/v1/glossary-terms/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  deleteGlossaryTerm: (id: string) => apiRequest<void>(`/api/v1/glossary-terms/${id}`, { method: "DELETE" }),
  correctTranscript: (meetingId: string) => apiRequest<TranscriptCorrectionResult>(`/api/v1/meetings/${meetingId}/transcript/correct`, { method: "POST" }),
  answerQuestion: (meetingId: string, questionId: string, answer: string | null, status: "answered" | "dismissed") =>
    apiRequest<MeetingQuestion>(`/api/v1/meetings/${meetingId}/questions/${questionId}`, { method: "PATCH", body: JSON.stringify({ answer, status }) }),
  editSegmentSpeaker: (meetingId: string, segmentId: string, speakerId: string, scope: "single" | "following") =>
    apiRequest<{ batch_id: string; changed_count: number }>(`/api/v1/meetings/${meetingId}/transcript-segments/${segmentId}/speaker`, { method: "PATCH", body: JSON.stringify({ speaker_id: speakerId, scope }) }),
  undoSpeakerEdit: (meetingId: string, batchId: string) =>
    apiRequest<{ batch_id: string; changed_count: number }>(`/api/v1/meetings/${meetingId}/speaker-edits/${batchId}/undo`, { method: "POST" }),
};

async function uploadResumable(input: UploadUrlResponse, file: File): Promise<void> {
  if (!supabase) throw new Error("파일 업로드 설정을 확인해 주세요.");
  const { data } = await supabase.auth.getSession();
  const accessToken = data.session?.access_token;
  const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim();
  const projectUrl = import.meta.env.VITE_SUPABASE_URL?.trim();
  if (!accessToken || !publishableKey || !projectUrl) {
    throw new Error("로그인 세션 또는 파일 업로드 설정을 확인해 주세요.");
  }
  const endpoint = new URL("/storage/v1/upload/resumable", projectUrl).toString();
  await new Promise<void>((resolve, reject) => {
    const upload = new tus.Upload(file, {
      endpoint,
      chunkSize: 6 * 1024 * 1024,
      retryDelays: [0, 3000, 5000, 10_000, 20_000],
      removeFingerprintOnSuccess: true,
      headers: {
        authorization: `Bearer ${accessToken}`,
        apikey: publishableKey,
        "x-upsert": "false",
      },
      metadata: {
        bucketName: input.bucket,
        objectName: input.path,
        contentType: input.file.mime_type,
      },
      onError: () => reject(new Error("파일을 업로드하지 못했어요. 다시 시도해 주세요.")),
      onSuccess: () => resolve(),
    });
    void upload.findPreviousUploads().then((previous) => {
      if (previous[0]) upload.resumeFromPreviousUpload(previous[0]);
      upload.start();
    }).catch(() => upload.start());
  });
}

export async function sha256File(file: File): Promise<string> {
  const digest = sha256.create();
  const chunkSize = 4 * 1024 * 1024;
  for (let offset = 0; offset < file.size; offset += chunkSize) {
    const chunk = await file.slice(offset, offset + chunkSize).arrayBuffer();
    digest.update(new Uint8Array(chunk));
  }
  return Array.from(digest.digest(), (byte) => byte.toString(16).padStart(2, "0")).join("");
}
