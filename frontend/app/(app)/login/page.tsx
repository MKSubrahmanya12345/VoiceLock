import { redirect } from "next/navigation";

// Auth removed for the demo: /login now just sends you to enrollment.
export default function LoginPage() {
  redirect("/enrollment");
}
