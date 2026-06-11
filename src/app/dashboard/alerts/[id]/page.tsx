import AlertDetailClient from "./AlertDetailClient";

export default async function AlertDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;
    return <AlertDetailClient alertId={id} />;
}
