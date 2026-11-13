import type { Team, TeamMember, User } from "@/types/api";

export const currentUser: User = {
  id: "user-minji",
  name: "김민지",
  email: "minji.kim@example.com",
  avatar_color: "bg-indigo-500",
};

export const mockTeams: Team[] = [
  {
    id: "team-ai-innovation",
    name: "AI Innovation Team",
    description: "더 나은 업무 경험을 만드는 제품 팀",
    member_count: 4,
    my_role: "member",
    organization: null,
    department: null,
  },
  {
    id: "team-product-lab",
    name: "Product Lab",
    description: "신규 제품 아이디어를 검증하는 워킹 그룹",
    member_count: 7,
    my_role: "member",
    organization: null,
    department: null,
  },
];

export const mockMembers: TeamMember[] = [
  { ...currentUser, role: "member" },
  {
    id: "user-seoyeon",
    name: "이서연",
    email: "seoyeon.lee@example.com",
    avatar_color: "bg-violet-500",
    role: "owner",
  },
  {
    id: "user-jihoon",
    name: "박지훈",
    email: "jihoon.park@example.com",
    avatar_color: "bg-sky-500",
    role: "admin",
  },
  {
    id: "user-yujin",
    name: "최유진",
    email: "yujin.choi@example.com",
    avatar_color: "bg-emerald-500",
    role: "member",
  },
];
