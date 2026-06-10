"use client";

import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { clearToken, getMe, getStoredToken, login as loginRequest, register as registerRequest, logout as clearAuthToken, storeToken } from "@/services/auth";
import type { AuthUser } from "@/services/auth";

type AuthContextValue = {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (payload: { email: string; password: string }) => Promise<AuthUser>;
  register: (payload: { name: string; email: string; password: string }) => Promise<AuthUser>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const bootstrap = async () => {
      const storedToken = getStoredToken();
      if (!storedToken) {
        clearAuthToken();
        setLoading(false);
        return;
      }
      setToken(storedToken);
      try {
        const me = await getMe(storedToken);
        if (me) {
          setUser(me);
          storeToken(storedToken);
        } else {
          clearAuthToken();
          setToken(null);
        }
      } catch {
        clearAuthToken();
        setUser(null);
        setToken(null);
      } finally {
        setLoading(false);
      }
    };
    void bootstrap();
  }, []);

  const setSession = (nextToken: string, nextUser: AuthUser) => {
    setToken(nextToken);
    setUser(nextUser);
    storeToken(nextToken);
  };

  const value = useMemo<AuthContextValue>(() => {
    return {
      user,
      token,
      loading,
      isAuthenticated: Boolean(user && token),
      login: async (payload) => {
        const result = await loginRequest(payload);
        setSession(result.access_token, result.user);
        return result.user;
      },
      register: async (payload) => {
        const result = await registerRequest(payload);
        setSession(result.access_token, result.user);
        return result.user;
      },
      logout: async () => {
        await clearToken();
        setUser(null);
        setToken(null);
      },
    };
  }, [loading, token, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
