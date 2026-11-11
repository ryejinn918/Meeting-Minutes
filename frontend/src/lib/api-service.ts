import { apiRequest } from "@/lib/api-client";
import type { Meeting, ProcessingJob, Team, TeamDetail, TeamMember, User } from "@/types/api";

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

function normalizeMember(member: TeamMember): TeamMember {
  return { ...member, avatar_color: member.avatar_color ?? avatarColor(member.id) };
}

export const apiService = {
  async getMe(): Promise<User> {
    const me = await apiRequest<MeApiResponse>("/api/v1/me");
    return normalizeUser({ id: me.id, name: me.display_name, email: me.email, avatar_url: me.avatar_url });
  },
  getTeams: () => apiRequest<Team[]>("/api/v1/teams"),
  createTeam: (name: string) => apiRequest<Team>("/api/v1/teams", { method: "POST", body: JSON.stringify({ name }) }),
  async getTeam(teamId: string): Promise<TeamDetail> {
    const team = await apiRequest<TeamDetail>(`/api/v1/teams/${teamId}`);
    return { ...team, members: team.members.map(normalizeMember) };
  },
  async getMeetings(teamId: string): Promise<Meeting[]> {
    const meetings = await apiRequest<Meeting[]>(`/api/v1/meetings?team_id=${encodeURIComponent(teamId)}`);
    return meetings.map(normalizeMeeting);
  },
  async getMeeting(id: string): Promise<Meeting> {
    return normalizeMeeting(await apiRequest<Meeting>(`/api/v1/meetings/${id}`));
  },
  async createMeeting(input: { team_id: string; title: string; meeting_at: string }): Promise<Meeting> {
    return normalizeMeeting(await apiRequest<Meeting>("/api/v1/meetings", {
      method: "POST",
      body: JSON.stringify({ ...input, source_type: "direct" }),
    }));
  },
  async updateMeeting(id: string, input: { title?: string; meeting_at?: string; version: number }): Promise<Meeting> {
    return normalizeMeeting(await apiRequest<Meeting>(`/api/v1/meetings/${id}`, { method: "PATCH", body: JSON.stringify(input) }));
  },
  async saveTranscript(id: string, text: string): Promise<Meeting> {
    return normalizeMeeting(await apiRequest<Meeting>(`/api/v1/meetings/${id}/transcript`, { method: "POST", body: JSON.stringify({ text }) }));
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
};
