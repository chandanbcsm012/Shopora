import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Footer from './components/Footer'
import Nav from './components/Nav'
import ProtectedRoute from './components/ProtectedRoute'
import RequireAdmin from './components/RequireAdmin'
import RequireRole from './components/RequireRole'
import { AuthProvider } from './context/AuthContext'
import { CartProvider } from './context/CartContext'
import { WishlistProvider } from './context/WishlistContext'
import AcceptInvitation from './pages/AcceptInvitation'
import About from './pages/About'
import AdminLayout from './pages/admin/AdminLayout'
import AuditLogs from './pages/admin/AuditLogs'
import Brands from './pages/admin/Brands'
import Categories from './pages/admin/Categories'
import AdminOrderDetail from './pages/admin/OrderDetail'
import AdminOrders from './pages/admin/Orders'
import ProductForm from './pages/admin/ProductForm'
import AdminProducts from './pages/admin/Products'
import Setup from './pages/admin/Setup'
import Users from './pages/admin/Users'
import Addresses from './pages/Addresses'
import Cart from './pages/Cart'
import Checkout from './pages/Checkout'
import Contact from './pages/Contact'
import CookiePolicy from './pages/CookiePolicy'
import FAQ from './pages/FAQ'
import ForgotPassword from './pages/ForgotPassword'
import Home from './pages/Home'
import Login from './pages/Login'
import MaintenancePage from './pages/MaintenancePage'
import NotFound from './pages/NotFound'
import OrderDetail from './pages/OrderDetail'
import Orders from './pages/Orders'
import PrivacyPolicy from './pages/PrivacyPolicy'
import ProductDetail from './pages/ProductDetail'
import ProductList from './pages/ProductList'
import RefundPolicy from './pages/RefundPolicy'
import Register from './pages/Register'
import ResetPassword from './pages/ResetPassword'
import ReturnPolicy from './pages/ReturnPolicy'
import ShippingPolicy from './pages/ShippingPolicy'
import TermsAndConditions from './pages/TermsAndConditions'
import Wishlist from './pages/Wishlist'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <CartProvider>
          <WishlistProvider>
            {/* Visually hidden until focused: lets keyboard/screen-reader users
                jump straight to the page content instead of tabbing through
                the nav (brand link, primary links, cart, auth links) on every
                single page. */}
            <a
              href="#main-content"
              className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-gray-900 focus:px-4 focus:py-2 focus:text-white"
            >
              Skip to content
            </a>
            <div className="flex min-h-screen flex-col bg-gray-50 text-gray-900">
              <Nav />
              <main id="main-content" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/products" element={<ProductList />} />
                  <Route path="/products/:id" element={<ProductDetail />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/register" element={<Register />} />
                  <Route path="/accept-invitation" element={<AcceptInvitation />} />
                  <Route path="/forgot-password" element={<ForgotPassword />} />
                  <Route path="/reset-password" element={<ResetPassword />} />
                  <Route
                    path="/cart"
                    element={
                      <ProtectedRoute>
                        <Cart />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/checkout"
                    element={
                      <ProtectedRoute>
                        <Checkout />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/orders"
                    element={
                      <ProtectedRoute>
                        <Orders />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/orders/:id"
                    element={
                      <ProtectedRoute>
                        <OrderDetail />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/addresses"
                    element={
                      <ProtectedRoute>
                        <Addresses />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/wishlist"
                    element={
                      <ProtectedRoute>
                        <Wishlist />
                      </ProtectedRoute>
                    }
                  />
                  <Route path="/about" element={<About />} />
                  <Route path="/contact" element={<Contact />} />
                  <Route path="/faq" element={<FAQ />} />
                  <Route path="/privacy-policy" element={<PrivacyPolicy />} />
                  <Route path="/terms-and-conditions" element={<TermsAndConditions />} />
                  <Route path="/shipping-policy" element={<ShippingPolicy />} />
                  <Route path="/return-policy" element={<ReturnPolicy />} />
                  <Route path="/refund-policy" element={<RefundPolicy />} />
                  <Route path="/cookie-policy" element={<CookiePolicy />} />
                  <Route path="/maintenance" element={<MaintenancePage />} />
                  {/* Standalone, public, full-page: not wrapped in AdminLayout's
                      tab bar since there's nothing to navigate to yet before
                      an admin account exists. */}
                  <Route path="/admin/setup" element={<Setup />} />
                  <Route
                    path="/admin"
                    element={
                      <RequireAdmin>
                        <AdminLayout />
                      </RequireAdmin>
                    }
                  >
                    <Route index element={<Navigate to="/admin/products" replace />} />
                    <Route path="categories" element={<Categories />} />
                    <Route path="brands" element={<Brands />} />
                    <Route path="products" element={<AdminProducts />} />
                    <Route path="products/new" element={<ProductForm />} />
                    <Route path="products/:id/edit" element={<ProductForm />} />
                    {/* Orders/Users/Audit Logs are admin+super_admin only —
                        RequireAdmin alone would also admit `manager` (needed
                        for catalog routes above), so these layer a stricter
                        RequireRole guard rather than navigating there by URL
                        past a hidden tab. */}
                    <Route
                      path="orders"
                      element={
                        <RequireRole roles={['admin', 'super_admin']}>
                          <AdminOrders />
                        </RequireRole>
                      }
                    />
                    <Route
                      path="orders/:id"
                      element={
                        <RequireRole roles={['admin', 'super_admin']}>
                          <AdminOrderDetail />
                        </RequireRole>
                      }
                    />
                    <Route
                      path="users"
                      element={
                        <RequireRole roles={['admin', 'super_admin']}>
                          <Users />
                        </RequireRole>
                      }
                    />
                    <Route
                      path="audit-logs"
                      element={
                        <RequireRole roles={['admin', 'super_admin']}>
                          <AuditLogs />
                        </RequireRole>
                      }
                    />
                  </Route>
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </main>
              <Footer />
            </div>
          </WishlistProvider>
        </CartProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
