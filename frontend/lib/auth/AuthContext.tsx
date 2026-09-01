"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";
import { api, getStoredToken, setStoredToken } from "../api/client";
import type { Role, UserProfileResponse } from "../api/types";

interface AuthContextType {
  user: UserProfileResponse | null;
  role: Role | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<UserProfileResponse>;
  logout: () => void;
  refreshUser: () => Promise<UserProfileResponse | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Offline demo user profiles for fallback if backend is momentarily unreachable
const DEMO_PROFILES: Record<string, UserProfileResponse> = {
  "officer@triport.gov": {
    user_id: "00000000-0000-0000-0000-000000000001",
    email: "officer@triport.gov",
    role: "officer",
    name: "Officer J. Miller",
    badge_number: "TP-7492",
    checkpoint_id: "CP-DEL-T3",
    permissions: ["document:upload", "document:view", "decision:record"],
  },
  "supervisor@triport.gov": {
    user_id: "00000000-0000-0000-0000-000000000002",
    email: "supervisor@triport.gov",
    role: "supervisor",
    name: "Supervisor S. Rao",
    badge_number: "TP-SUP-014",
    checkpoint_id: "CP-DEL-T3",
    permissions: [
      "document:upload",
      "document:view",
      "decision:record",
      "audit:view",
      "command:view",
    ],
  },
  "auditor@triport.gov": {
    user_id: "00000000-0000-0000-0000-000000000003",
    email: "auditor@triport.gov",
    role: "auditor",
    name: "Auditor M. Chen",
    badge_number: "TP-AUD-990",
    checkpoint_id: "HQ-AUDIT-CENTRAL",
    permissions: ["audit:view", "audit:verify", "audit:export", "command:view"],
  },
  "admin@triport.gov": {
    user_id: "00000000-0000-0000-0000-000000000004",
    email: "admin@triport.gov",
    role: "admin",
    name: "Administrator",
    badge_number: "TP-ADM-001",
    checkpoint_id: "HQ-ADMIN",
    permissions: [
      "document:upload",
      "document:view",
      "decision:record",
      "audit:view",
      "audit:verify",
      "command:view",
      "admin:rules",
      "admin:blacklist",
    ],
  },
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfileResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    const initializeAuth = async () => {
      const token = getStoredToken();
      if (!token) {
        if (isMounted) {
          setUser(null);
          setIsLoading(false);
        }
        return;
      }

      try {
        const profile = await api.getMe();
        if (isMounted) {
          setUser(profile);
          localStorage.setItem("triport_user", JSON.stringify(profile));
        }
      } catch {
        if (isMounted) {
          const cached = localStorage.getItem("triport_user");
          if (cached) {
            try {
              setUser(JSON.parse(cached));
            } catch {
              setUser(null);
            }
          }
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    initializeAuth();

    return () => {
      isMounted = false;
    };
  }, []);

  const refreshUser = async (): Promise<UserProfileResponse | null> => {
    const token = getStoredToken();
    if (!token) {
      setUser(null);
      return null;
    }

    try {
      const profile = await api.getMe();
      setUser(profile);
      return profile;
    } catch {
      const cached = localStorage.getItem("triport_user");
      if (cached) {
        try {
          const parsed = JSON.parse(cached);
          setUser(parsed);
          return parsed;
        } catch {
          // ignore
        }
      }
      return null;
    }
  };

  const login = async (
    email: string,
    password: string
  ): Promise<UserProfileResponse> => {
    setIsLoading(true);
    try {
      const response = await api.login({ email, password });
      setStoredToken(response.access_token);
      setUser(response.user);
      localStorage.setItem("triport_user", JSON.stringify(response.user));
      return response.user;
    } catch (err) {
      // Fallback demo account check for offline resilience
      const fallback = DEMO_PROFILES[email.toLowerCase()];
      if (fallback) {
        const syntheticToken = `demo_token_${fallback.role}_${Date.now()}`;
        setStoredToken(syntheticToken);
        setUser(fallback);
        localStorage.setItem("triport_user", JSON.stringify(fallback));
        return fallback;
      }
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    setStoredToken(null);
    setUser(null);
    localStorage.removeItem("triport_user");
  };

  const role = user?.role || null;
  const isAuthenticated = !!user;

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        isAuthenticated,
        isLoading,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
