import { createFileRoute } from "@tanstack/react-router";
import { CraftApp } from "@/craft/CraftApp";

export const Route = createFileRoute("/craft")({
  component: CraftPage,
});

function CraftPage() {
  return <CraftApp />;
}
