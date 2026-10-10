"use client";

import React, { use, Suspense } from "react";
import { useRouter } from "next/navigation";
import { ProductDossierModal } from "@/components/products/ProductDossierModal";

function ProductDossierContent({
  paramsPromise,
}: {
  paramsPromise: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const resolved = use(paramsPromise);
  const productId = resolved.id;

  return (
    <div className="min-h-screen py-6">
      <ProductDossierModal
        productId={productId}
        onClose={() => router.push("/products")}
      />
    </div>
  );
}

export default function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <Suspense
      fallback={
        <div className="p-12 text-center text-slate-400">
          Loading product dossier...
        </div>
      }
    >
      <ProductDossierContent paramsPromise={params} />
    </Suspense>
  );
}

