import { lazy } from "react";
import { Navigate, type RouteObject } from "react-router-dom";
const ApplicationsPage=lazy(()=>import("./pages/ApplicationsPage"));
const MyApplicationsPage=lazy(()=>import("./pages/MyApplicationsPage"));
const ReportsPage=lazy(()=>import("./pages/ReportsPage"));
const AttorneyPanelPage=lazy(()=>import("./pages/AttorneyPanelPage"));
export const routes:RouteObject[]=[{index:true,element:<Navigate to="my-applications" replace/>},{path:"my-applications",element:<MyApplicationsPage/>},{path:"applications",element:<ApplicationsPage/>},{path:"reports",element:<ReportsPage/>},{path:"attorneys",element:<AttorneyPanelPage/>}];
