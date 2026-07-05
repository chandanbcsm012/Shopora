import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import * as catalogApi from '../api/catalog'
import type { Brand, Category, Product } from '../api/types'
import { ProductCard, ProductCardSkeleton } from '../components/ProductCard'
import { Button, Skeleton } from '../components/ui'
import { cn } from '../lib/cn'

const NEW_ARRIVALS_PAGE_SIZE = 8
const SLIDE_INTERVAL_MS = 5000

interface HeroSlide {
  title: string
  subtitle: string
  ctaLabel: string
  ctaTo: string
  imageUrl?: string
}

// Static marketing copy — no CMS/backend needed for this. `imageUrl` is
// filled in from real category/product images once they load (see
// `heroSlides` below); a slide with no image available falls back to a CSS
// gradient rather than a hardcoded stock photo.
const HERO_COPY: Omit<HeroSlide, 'imageUrl'>[] = [
  {
    title: 'Everything you need, one storefront',
    subtitle: 'Quality products across every category, with simple checkout and honest pricing.',
    ctaLabel: 'Shop all products',
    ctaTo: '/products',
  },
  {
    title: 'Just landed: new arrivals',
    subtitle: 'Fresh stock added regularly — see what showed up this week.',
    ctaLabel: 'See new arrivals',
    ctaTo: '/products',
  },
  {
    title: 'Shop by category',
    subtitle: 'Browse a focused catalog organized the way you shop.',
    ctaLabel: 'Browse categories',
    ctaTo: '/products',
  },
  {
    title: 'Simple, secure checkout',
    subtitle: 'Pay by Cash on Delivery or our secure test-card flow — your choice.',
    ctaLabel: 'Start shopping',
    ctaTo: '/products',
  },
]

export default function Home() {
  const [categories, setCategories] = useState<Category[]>([])
  const [categoriesLoaded, setCategoriesLoaded] = useState(false)
  const [newArrivals, setNewArrivals] = useState<Product[]>([])
  const [newArrivalsLoaded, setNewArrivalsLoaded] = useState(false)
  const [brands, setBrands] = useState<Brand[]>([])
  const [brandsLoaded, setBrandsLoaded] = useState(false)

  useEffect(() => {
    catalogApi
      .listCategories()
      .then(setCategories)
      .catch(() => setCategories([]))
      .finally(() => setCategoriesLoaded(true))

    catalogApi
      .listProducts({ sort: 'newest', page_size: NEW_ARRIVALS_PAGE_SIZE })
      .then((result) => setNewArrivals(result.items))
      .catch(() => setNewArrivals([]))
      .finally(() => setNewArrivalsLoaded(true))

    catalogApi
      .listBrands()
      .then(setBrands)
      .catch(() => setBrands([]))
      .finally(() => setBrandsLoaded(true))
  }, [])

  // Prefer real category images, then real product images, for the hero
  // slider — never a hardcoded external stock-photo URL. A slide with no
  // image available yet (or none exists) renders a gradient instead.
  const heroSlides = useMemo<HeroSlide[]>(() => {
    const categoryImages = categories.map((c) => c.image_url).filter((url): url is string => Boolean(url))
    const productImages = newArrivals.flatMap((p) => (p.images ?? []).map((img) => img.url))
    const imagePool = [...categoryImages, ...productImages]
    return HERO_COPY.map((copy, index) => ({ ...copy, imageUrl: imagePool[index] }))
  }, [categories, newArrivals])

  return (
    <div className="flex flex-col gap-14">
      <HeroSlider slides={heroSlides} />

      {(!categoriesLoaded || categories.length > 0) && (
        <section aria-labelledby="shop-by-category">
          <h2 id="shop-by-category" className="mb-4 text-xl font-semibold tracking-tight text-gray-900">
            Shop by category
          </h2>
          {!categoriesLoaded ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4" aria-hidden="true">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="aspect-square w-full" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {categories.map((category) => (
                <Link
                  key={category.id}
                  to={`/products?category_id=${category.id}`}
                  className="group overflow-hidden rounded-lg border border-gray-200 bg-white"
                >
                  <div className="aspect-square w-full overflow-hidden bg-gray-100">
                    {category.image_url ? (
                      <img
                        src={category.image_url}
                        alt=""
                        loading="lazy"
                        className="h-full w-full object-cover transition-transform group-hover:scale-105"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-xs text-gray-400">
                        No image
                      </div>
                    )}
                  </div>
                  <p className="p-3 text-sm font-medium text-gray-900">{category.name}</p>
                </Link>
              ))}
            </div>
          )}
        </section>
      )}

      {(!newArrivalsLoaded || newArrivals.length > 0) && (
        <section aria-labelledby="new-arrivals">
          <div className="mb-4 flex items-center justify-between">
            <h2 id="new-arrivals" className="text-xl font-semibold tracking-tight text-gray-900">
              New arrivals
            </h2>
            <Link to="/products" className="text-sm font-medium text-brand-600 hover:text-brand-700">
              Shop all &rarr;
            </Link>
          </div>
          {!newArrivalsLoaded ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4" aria-hidden="true">
              {Array.from({ length: NEW_ARRIVALS_PAGE_SIZE }).map((_, i) => (
                <ProductCardSkeleton key={i} />
              ))}
            </div>
          ) : (
            <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {newArrivals.map((product) => (
                <li key={product.id}>
                  <ProductCard product={product} />
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {(!brandsLoaded || brands.length > 0) && (
        <section aria-labelledby="shop-by-brand">
          <h2 id="shop-by-brand" className="mb-4 text-xl font-semibold tracking-tight text-gray-900">
            Shop by brand
          </h2>
          {!brandsLoaded ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6" aria-hidden="true">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
              {brands.map((brand) => (
                <Link
                  key={brand.id}
                  to={`/products?brand_id=${brand.id}`}
                  className="flex h-16 items-center justify-center rounded-lg border border-gray-200 bg-white px-3 text-center text-sm font-medium text-gray-700 hover:border-brand-600 hover:text-brand-600"
                >
                  {brand.name}
                </Link>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}

/**
 * Auto-rotating hero banner. Plain React state + setInterval per this app's
 * "no new dependencies" constraint — no carousel library. Pauses on hover,
 * supports manual prev/next and dot navigation, and every control is a real
 * `<button>` with an `aria-label` for keyboard/screen-reader users.
 */
function HeroSlider({ slides }: { slides: HeroSlide[] }) {
  const [activeIndex, setActiveIndex] = useState(0)
  const [isPaused, setIsPaused] = useState(false)

  useEffect(() => {
    if (isPaused || slides.length <= 1) return
    const handle = setInterval(() => {
      setActiveIndex((i) => (i + 1) % slides.length)
    }, SLIDE_INTERVAL_MS)
    return () => clearInterval(handle)
  }, [isPaused, slides.length])

  // Clamp the active index whenever the slide count changes (shouldn't
  // happen after mount here, but keeps this safe if it ever does).
  useEffect(() => {
    if (activeIndex >= slides.length) setActiveIndex(0)
  }, [slides.length, activeIndex])

  function goTo(index: number) {
    setActiveIndex(((index % slides.length) + slides.length) % slides.length)
  }

  const slide = slides[activeIndex]
  if (!slide) return null

  return (
    <section
      aria-label="Featured promotions"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      className="relative overflow-hidden rounded-lg"
    >
      <div className="relative flex min-h-[320px] items-center overflow-hidden rounded-lg sm:min-h-[400px]">
        {slide.imageUrl ? (
          <img
            key={slide.imageUrl}
            src={slide.imageUrl}
            alt=""
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover"
          />
        ) : (
          <div className="absolute inset-0 bg-gradient-to-br from-brand-600 to-brand-800" />
        )}
        <div className="absolute inset-0 bg-black/40" />
        <div className="relative z-10 max-w-xl px-6 py-12 text-white sm:px-12">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{slide.title}</h1>
          <p className="mt-3 text-base text-white/90">{slide.subtitle}</p>
          <Link to={slide.ctaTo}>
            <Button className="mt-6">{slide.ctaLabel}</Button>
          </Link>
        </div>
      </div>

      {slides.length > 1 && (
        <>
          <button
            type="button"
            aria-label="Previous slide"
            onClick={() => goTo(activeIndex - 1)}
            className="absolute left-3 top-1/2 z-20 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-gray-900 hover:bg-white"
          >
            &larr;
          </button>
          <button
            type="button"
            aria-label="Next slide"
            onClick={() => goTo(activeIndex + 1)}
            className="absolute right-3 top-1/2 z-20 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-gray-900 hover:bg-white"
          >
            &rarr;
          </button>
          <div className="absolute bottom-3 left-1/2 z-20 flex -translate-x-1/2 gap-2">
            {slides.map((s, index) => (
              <button
                key={s.title}
                type="button"
                aria-label={`Go to slide ${index + 1}`}
                aria-current={index === activeIndex}
                onClick={() => goTo(index)}
                className={cn('h-2 w-2 rounded-full', index === activeIndex ? 'bg-white' : 'bg-white/50')}
              />
            ))}
          </div>
        </>
      )}
    </section>
  )
}
