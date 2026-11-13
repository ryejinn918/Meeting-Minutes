export const queryKeys = {
  me: ["me"] as const,
  teams: ["teams"] as const,
  organizations: ["organizations"] as const,
  organization: (organizationId: string) => ["organizations", organizationId] as const,
  team: (teamId: string) => ["teams", teamId] as const,
  teamMembers: (teamId: string) => ["teams", teamId, "members"] as const,
  meetings: (teamId: string) => ["meetings", teamId] as const,
  meeting: (meetingId: string) => ["meetings", "detail", meetingId] as const,
  meetingFiles: (meetingId: string) => ["meetings", "detail", meetingId, "files"] as const,
  qualityOptions: (teamId: string) => ["teams", teamId, "quality-options"] as const,
  job: (jobId: string) => ["jobs", jobId] as const,
};
