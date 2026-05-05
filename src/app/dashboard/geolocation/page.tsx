import { initAuth } from "@/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { headers } from "next/headers";
import { MapPin, Clock, Globe, Building, Server, Navigation } from "lucide-react";

export default async function GeolocationPage() {
    const authInstance = await initAuth();
    const cloudflareGeolocationData = await authInstance.api.getGeolocation({ headers: await headers() });

    return (
        <Card className="w-full">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-xl font-semibold">
                    <MapPin className="h-5 w-5" />
                    Your Location
                </CardTitle>
                <p className="text-sm text-gray-600">Automatically detected using Cloudflare&apos;s global network</p>
            </CardHeader>
            <CardContent>
                {cloudflareGeolocationData && "error" in cloudflareGeolocationData && (
                    <div className="flex items-center gap-2 p-4 bg-red-50 rounded-lg">
                        <div className="text-red-500">&#x26A0;&#xFE0F;</div>
                        <p className="text-red-700">
                            <strong>Error:</strong> {cloudflareGeolocationData.error}
                        </p>
                    </div>
                )}
                {cloudflareGeolocationData && !("error" in cloudflareGeolocationData) && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="flex items-center gap-3 p-2">
                            <Clock className="h-5 w-5 text-gray-600" />
                            <div>
                                <p className="font-medium text-gray-900">Timezone</p>
                                <p className="text-gray-600">{cloudflareGeolocationData.timezone || "Unknown"}</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 p-2">
                            <Building className="h-5 w-5 text-gray-600" />
                            <div>
                                <p className="font-medium text-gray-900">City</p>
                                <p className="text-gray-600">{cloudflareGeolocationData.city || "Unknown"}</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 p-2">
                            <Globe className="h-5 w-5 text-gray-600" />
                            <div>
                                <p className="font-medium text-gray-900">Country</p>
                                <p className="text-gray-600">{cloudflareGeolocationData.country || "Unknown"}</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 p-2">
                            <MapPin className="h-5 w-5 text-gray-600" />
                            <div>
                                <p className="font-medium text-gray-900">Region</p>
                                <p className="text-gray-600">
                                    {cloudflareGeolocationData.region || "Unknown"}
                                    {cloudflareGeolocationData.regionCode &&
                                        ` (${cloudflareGeolocationData.regionCode})`}
                                </p>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 p-2">
                            <Server className="h-5 w-5 text-gray-600" />
                            <div>
                                <p className="font-medium text-gray-900">Data Center</p>
                                <p className="text-gray-600">{cloudflareGeolocationData.colo || "Unknown"}</p>
                            </div>
                        </div>

                        {(cloudflareGeolocationData.latitude || cloudflareGeolocationData.longitude) && (
                            <div className="flex items-center gap-3 p-2">
                                <Navigation className="h-5 w-5 text-gray-600" />
                                <div>
                                    <p className="font-medium text-gray-900">Coordinates</p>
                                    <p className="text-gray-600">
                                        {cloudflareGeolocationData.latitude && cloudflareGeolocationData.longitude
                                            ? `${cloudflareGeolocationData.latitude}, ${cloudflareGeolocationData.longitude}`
                                            : "Partially available"}
                                    </p>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
