import { z } from "zod";

const serverSchema = z.object({
  API_BASE_URL: z.string().url().default("http://127.0.0.1:8000"),
});

export const serverEnv = serverSchema.parse({
  API_BASE_URL: process.env.API_BASE_URL,
});

export { serverSchema };
