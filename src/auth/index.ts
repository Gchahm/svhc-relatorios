import { getCloudflareContext } from "@opennextjs/cloudflare";
import { betterAuth } from "better-auth";
import { withCloudflare } from "better-auth-cloudflare";
import { drizzleAdapter } from "@better-auth/drizzle-adapter";
import { openAPI } from "better-auth/plugins";
import type { D1Database } from "@cloudflare/workers-types";
import { getDb } from "../db";

// Define an asynchronous function to build your auth configuration
async function authBuilder() {
    const dbInstance = await getDb();
    const cfCtx = getCloudflareContext();
    return betterAuth({
        ...withCloudflare(
            {
                autoDetectIpAddress: true,
                geolocationTracking: true,
                cf: cfCtx.cf,
                d1: {
                    db: dbInstance,
                    options: {
                        usePlural: true,
                        debugLogs: true,
                    },
                },
                kv: cfCtx.env.KV,
            },
            {
                baseURL: cfCtx.env.BETTER_AUTH_URL,
                trustedOrigins: (cfCtx.env.BETTER_AUTH_TRUSTED_ORIGINS ?? "").split(",").filter(Boolean),
                emailAndPassword: {
                    enabled: true,
                },
                rateLimit: {
                    enabled: true,
                    window: 60,
                    max: 100,
                },
                plugins: [openAPI()],
            }
        ),
    });
}

// Singleton pattern to ensure a single auth instance
let authInstance: Awaited<ReturnType<typeof authBuilder>> | null = null;

// Asynchronously initializes and retrieves the shared auth instance
export async function initAuth() {
    if (!authInstance) {
        authInstance = await authBuilder();
    }
    return authInstance;
}

/* ======================================================================= */
/* Configuration for Schema Generation                                     */
/* ======================================================================= */

// This simplified configuration is used by the Better Auth CLI for schema generation.
// It includes only the options that affect the database schema.
// It's necessary because the main `authBuilder` performs operations (like `getDb()`)
// which use `getCloudflareContext` (not available in a CLI context only on Cloudflare).
// For more details, see: https://www.answeroverflow.com/m/1362463260636479488
export const auth = betterAuth({
    ...withCloudflare(
        {
            autoDetectIpAddress: true,
            geolocationTracking: true,
            cf: {},
        },
        {
            emailAndPassword: {
                enabled: true,
            },
            plugins: [openAPI()],
        }
    ),

    // Used by the Better Auth CLI for schema generation.
    database: drizzleAdapter({} as D1Database, {
                      provider: "sqlite",
                      usePlural: true,
                      debugLogs: true
                  }),
});
