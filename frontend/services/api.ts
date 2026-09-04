import { SessionStatus, SessionResponse, RiskResponse } from '@/types';
import { getAccessToken, getSupabase } from '@/lib/supabase';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function getAuthHeaders(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function detailOf(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
  }
  return fallback;
}

export interface EnrollmentInfo {
  enrolled: boolean;
  user_id: string;
  name?: string;
  embedding_dimension?: number;
  audio_duration?: number;
}

export const apiService = {
  async createSession(): Promise<SessionResponse> {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...headers
      },
    });

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(detailOf(body, 'Failed to create session'));
    }

    return response.json();
  },

  async getSessionRisk(sessionId: string): Promise<RiskResponse> {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/risk`, {
      headers: { ...headers },
    });

    if (!response.ok) {
      throw new Error('Failed to get risk assessment');
    }

    return response.json();
  },

  async enrollUser(name: string, audioBlob: Blob): Promise<EnrollmentInfo & { status: string; message: string }> {
    const headers = await getAuthHeaders();
    const formData = new FormData();
    formData.append('name', name);
    formData.append('audio', audioBlob, 'enrollment.wav');

    const response = await fetch(`${API_BASE_URL}/enrollment/create`, {
      method: 'POST',
      headers: { ...headers },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new Error(detailOf(error, 'Enrollment failed'));
    }

    return response.json();
  },

  /** The authenticated caller's own enrollment (name, voiceprint status). */
  async getMyEnrollment(): Promise<EnrollmentInfo> {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/enrollment/me`, {
      headers: { ...headers },
    });

    if (response.status === 401) {
      // Signed out or expired session - drop local state so AuthGuard re-routes.
      await getSupabase().auth.signOut().catch(() => {});
      throw new Error('Your session expired. Please sign in again.');
    }

    if (!response.ok) {
      throw new Error('Failed to check enrollment');
    }

    return response.json();
  },

  /** Delete the authenticated caller's own enrollment. */
  async deleteMyEnrollment(): Promise<void> {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/enrollment/me`, {
      method: 'DELETE',
      headers: { ...headers },
    });

    if (!response.ok && response.status !== 404) {
      const error = await response.json().catch(() => null);
      throw new Error(detailOf(error, 'Failed to delete enrollment'));
    }
  },
};
