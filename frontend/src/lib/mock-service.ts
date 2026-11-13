import { initialMeetings } from "@/features/meetings/mock-data";
import { currentUser, mockMembers, mockTeams } from "@/features/teams/mock-teams";
import type { ActionItem, Meeting, MockSession, Team, TeamMember } from "@/types/api";

const wait = (milliseconds = 240) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));
let meetings = structuredClone(initialMeetings);
let teams = structuredClone(mockTeams);

export const mockService = {
  async login(email: string, password: string): Promise<MockSession> {
    await wait();
    if (!email || password.length < 6) throw new Error("이메일과 6자 이상의 비밀번호를 입력해 주세요.");
    return { user: { ...currentUser, email }, is_mock: true };
  },

  async signup(name: string, email: string, password: string): Promise<MockSession> {
    await wait();
    if (!name.trim() || !email.includes("@") || password.length < 8) throw new Error("입력값을 다시 확인해 주세요.");
    return { user: { ...currentUser, name, email }, is_mock: true };
  },

  async getTeams(): Promise<Team[]> {
    await wait();
    return structuredClone(teams);
  },

  async createTeam(name: string): Promise<Team> {
    await wait();
    const team: Team = { id: `team-${Date.now()}`, name, description: "새로 만든 Mock 팀", member_count: 1, my_role: "owner", organization: null, department: null };
    teams = [team, ...teams];
    return structuredClone(team);
  },

  async getMembers(): Promise<TeamMember[]> {
    await wait();
    return structuredClone(mockMembers);
  },

  async getMeetings(teamId: string): Promise<Meeting[]> {
    await wait();
    return structuredClone(meetings.filter((meeting) => meeting.team_id === teamId));
  },

  async getMeeting(id: string): Promise<Meeting> {
    await wait();
    const meeting = meetings.find((item) => item.id === id);
    if (!meeting) throw new Error("회의록을 찾을 수 없습니다.");
    return structuredClone(meeting);
  },

  async createMeeting(input: Pick<Meeting, "team_id" | "title" | "meeting_at" | "transcript_original">): Promise<Meeting> {
    await wait(420);
    const id = `meeting-${Date.now()}`;
    const meeting: Meeting = {
      topic: "",
      location: "",
      meeting_type: "general",
      purpose: "",
      project_name: "",
      template_id: null,
      metadata_confirmed_at: null,
      attendees: [],
      transcript_corrected: "",
      questions: [],
      latest_speaker_edit_batch_id: null,
      id,
      team_id: input.team_id,
      title: input.title,
      meeting_at: input.meeting_at,
      transcript_original: input.transcript_original,
      transcript_edited: input.transcript_original,
      transcript_speakers: [],
      transcript_segments: [],
      created_by: currentUser,
      processing_status: "analyzing",
      is_mine: true,
      is_shared_with_me: false,
      summary: "Mock 분석 결과를 준비하고 있습니다.",
      key_discussions: [],
      decisions: [],
      follow_ups: [],
      action_items: [],
      shared_member_ids: [],
      ai_generated_at: null,
      version: 1,
    };
    meetings = [meeting, ...meetings];
    return structuredClone(meeting);
  },

  async updateMeeting(id: string, patch: Partial<Pick<Meeting, "summary" | "transcript_edited" | "key_discussions" | "decisions" | "follow_ups">>): Promise<Meeting> {
    await wait(500);
    meetings = meetings.map((meeting) => (meeting.id === id ? { ...meeting, ...patch } : meeting));
    return this.getMeeting(id);
  },

  async updateAction(meetingId: string, action: ActionItem): Promise<ActionItem> {
    await wait();
    meetings = meetings.map((meeting) => meeting.id === meetingId ? { ...meeting, action_items: meeting.action_items.map((item) => item.id === action.id ? action : item) } : meeting);
    return structuredClone(action);
  },

  async updateShares(meetingId: string, memberIds: string[]): Promise<string[]> {
    await wait(500);
    meetings = meetings.map((meeting) => meeting.id === meetingId ? { ...meeting, shared_member_ids: [...memberIds] } : meeting);
    return [...memberIds];
  },
};
