import { Navigate, useLocation } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'

function ProtectedRoute({ children }) {
    const location = useLocation()
    const token = localStorage.getItem('access_token')

    if (!token) {
        return (
            <Navigate
                to="/login"
                replace
                state={{ from: location }}
            />
        )
    }

    return children
}

export default ProtectedRoute