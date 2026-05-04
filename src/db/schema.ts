import * as authSchema from "./auth.schema";
import * as fiscalSchema from "./fiscal.schema";

// Combine all schemas here for migrations
export const schema = {
    ...authSchema,
    ...fiscalSchema,
} as const;
