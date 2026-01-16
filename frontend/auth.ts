import { getCurrentUserInfoApiUsersMeGet, UserRole } from '@/lib/generated-api';
import { JWTPayload, SignJWT } from 'jose';
import NextAuth from 'next-auth';
import Google from 'next-auth/providers/google';
import MicrosoftEntraID from 'next-auth/providers/microsoft-entra-id';
import { baseUrl } from './lib/api';

export const { handlers, signIn, signOut, auth } = NextAuth({
  theme: {
    colorScheme: 'light',
  },
  providers: [
    ...(process.env.AUTH_GOOGLE_ID
      ? [
          Google({
            clientId: process.env.AUTH_GOOGLE_ID,
            clientSecret: process.env.AUTH_GOOGLE_SECRET,
          }),
        ]
      : []),
    ...(process.env.AUTH_MICROSOFT_ENTRA_ID_ID
      ? [
          MicrosoftEntraID({
            clientId: process.env.AUTH_MICROSOFT_ENTRA_ID_ID,
            clientSecret: process.env.AUTH_MICROSOFT_ENTRA_ID_SECRET,
            issuer: process.env.AUTH_MICROSOFT_ENTRA_ID_ISSUER,
          }),
        ]
      : []),
  ],
  callbacks: {
    jwt: async ({ token, account, user, profile }) => {
      // Only fetch user info on initial sign-in (when account is present)
      if (account) {
        token.uid = `${account.provider}:${account.providerAccountId}`;
        token.email = user?.email ?? profile?.email;
        token.name = user?.name ?? profile?.name;
        token.provider = account.provider;

        // Fetch and store the user's role in the token (only on sign-in)
        const accessToken = await createAccessToken(token);
        const role = await fetchUserRole(accessToken);
        token.role = role;
      }
      return token;
    },
    session: async ({ session, token }) => {
      const accessToken = await createAccessToken(token);

      return {
        ...session,
        accessToken,
        user: {
          ...session.user,
          role: (token.role as UserRole) ?? UserRole.User,
        },
      };
    },
  },
});

async function createAccessToken(token: Record<string, unknown>): Promise<string> {
  const payload: JWTPayload = {
    sub: token.uid as string,
    email: token.email as string,
    name: token.name as string,
    provider: token.provider as string,
    iss: 'ai-reviewer',
    aud: 'ai-reviewer-api',
  };
  return new SignJWT(payload)
    .setProtectedHeader({
      alg: 'HS512',
      typ: 'JWT',
    })
    .setIssuedAt()
    .setExpirationTime('15m')
    .sign(new TextEncoder().encode(process.env.AUTH_SECRET!));
}

async function fetchUserRole(accessToken: string): Promise<UserRole> {
  try {
    const response = await getCurrentUserInfoApiUsersMeGet({
      baseUrl,
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });
    return response.role;
  } catch (error) {
    console.error('Failed to fetch user role:', error);
  }
  return UserRole.User;
}

declare module 'next-auth' {
  interface Session {
    accessToken?: string;
  }
  interface User {
    role: UserRole;
  }
}
