"use client";

import Image from "next/image";
import { useState } from "react";

import type { Photo as PhotoData } from "@/lib/images";

type Props = {
  photo: PhotoData | null;
  alt: string;
  sizes: string;
  priority?: boolean;
  className?: string;
  /** Shown on the plain tile when no relevant photograph exists. */
  label?: string;
  position?: string;
};

/**
 * Responsive, lazy photograph. When there is no relevant image (or it fails to load)
 * it renders a neutral sand tile with the place name instead of a wrong picture.
 */
export function Photo({ photo, alt, sizes, priority, className = "", label, position }: Props) {
  const [failed, setFailed] = useState(false);
  const show = photo && !failed;
  return (
    <div className={`dj-photo ${className}`} role={show ? undefined : "img"} aria-label={show ? undefined : alt}>
      {show ? (
        <Image
          src={photo.src}
          alt={alt}
          fill
          sizes={sizes}
          priority={priority}
          unoptimized
          style={position ? { objectPosition: position } : undefined}
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="dj-photo-fallback">{label}</div>
      )}
    </div>
  );
}
