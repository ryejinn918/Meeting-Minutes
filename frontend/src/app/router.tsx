import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "@/components/shared/app-layout";
import { ActionsPage } from "@/pages/actions-page";
import { LoginPage } from "@/pages/login-page";
import { MeetingDetailPage } from "@/pages/meeting-detail-page";
import { MeetingNewPage } from "@/pages/meeting-new-page";
import { MeetingsPage } from "@/pages/meetings-page";
import { NotFoundPage } from "@/pages/not-found-page";
import { OrganizationsPage } from "@/pages/organizations-page";
import { ProcessingPage } from "@/pages/processing-page";
import { SharePage } from "@/pages/share-page";
import { SignupPage } from "@/pages/signup-page";
import { TeamNewPage } from "@/pages/team-new-page";
import { TeamSettingsPage } from "@/pages/team-settings-page";
import { TeamsPage } from "@/pages/teams-page";
import { GuestRoute, ProtectedRoute } from "@/features/auth/route-guards";

export const router = createBrowserRouter([
  { path: "/", element: <Navigate replace to="/login" /> },
  {
    element: <GuestRoute />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/signup", element: <SignupPage /> },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      { path: "/teams", element: <TeamsPage /> },
      { path: "/teams/new", element: <TeamNewPage /> },
      { path: "/organizations", element: <OrganizationsPage /> },
      {
        element: <AppLayout />,
        children: [
          { path: "/t/:teamId/meetings", element: <MeetingsPage /> },
          { path: "/t/:teamId/meetings/new", element: <MeetingNewPage /> },
          { path: "/meetings/:id/processing", element: <ProcessingPage /> },
          { path: "/meetings/:id", element: <MeetingDetailPage /> },
          { path: "/meetings/:id/share", element: <SharePage /> },
          { path: "/t/:teamId/settings", element: <TeamSettingsPage /> },
          { path: "/actions", element: <ActionsPage /> },
        ],
      },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
