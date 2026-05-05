import { initAuth } from "@/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { headers } from "next/headers";

export default async function DashboardPage() {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });

    // Session is guaranteed by layout, but TypeScript needs the check
    if (!session) return null;

    return (
        <Card className="w-full">
            <CardHeader>
                <CardTitle className="text-xl font-semibold">User Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <p className="text-lg">
                    Welcome, <span className="font-semibold">{session.user?.name || session.user?.email}</span>!
                </p>
                {session.user?.email && (
                    <p className="text-md break-words">
                        <strong>Email:</strong> <span className="break-all">{session.user.email}</span>
                    </p>
                )}
                {session.user?.id && (
                    <p className="text-md">
                        <strong>User ID:</strong> {session.user.id}
                    </p>
                )}
            </CardContent>
        </Card>
    );
}
